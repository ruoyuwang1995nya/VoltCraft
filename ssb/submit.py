import glob
import shutil
import os.path
import tempfile
import logging
from multiprocessing import Pool
from dflow import config, s3_config
from monty.serialization import loadfn
import fpop, dpdata, apex #phonolammps
from .config import Config
from apex.archive import archive_workdir
import ssb
from .op.property_ops import PropsMake, PropsPost
from .flow import FlowGenerator
from .op.eval_ops import DPValidate#direct_inference
import logging
import shutil

from apex.utils import (
    judge_flow,
    load_config_file,
    json2dict,
    copy_all_other_files,
    sepline,
    handle_prop_suffix,
    backup_path
)


def pack_upload_dir(
        work_dir: os.PathLike,
        upload_dir: os.PathLike,
        relax_param: dict,
        prop_param: dict,
        flow_type: str
):
    """
    Pack the necessary files and directories into temp dir and upload it to dflow
    """
    cwd = os.getcwd()
    os.chdir(work_dir)
    relax_confs = relax_param.get("structures", []) if relax_param else []
    prop_confs = prop_param.get("structures", []) if prop_param else []
    relax_prefix = relax_param["interaction"].get("potcar_prefix", None) if relax_param else None
    prop_prefix = prop_param["interaction"].get("potcar_prefix", None) if prop_param else None
    include_dirs = set()
    if relax_prefix:
        relax_prefix_base = relax_prefix.split('/')[0]
        include_dirs.add(relax_prefix_base)
    if prop_prefix:
        prop_prefix_base = prop_prefix.split('/')[0]
        include_dirs.add(prop_prefix_base)
    confs = relax_confs + prop_confs
    assert len(confs) > 0, "No configuration path indicated!"
    conf_dirs = []
    for conf in confs:
        conf_dirs.extend(glob.glob(conf))
    conf_dirs = list(set(conf_dirs))
    conf_dirs.sort()
    refine_init_name_list = []
    # backup all existing property work directories
    if flow_type in ['props', 'joint']:
        property_list = prop_param["properties"]
        for ii in conf_dirs:
            sepline(ch=ii, screen=True)
            for jj in property_list:
                do_refine, suffix = handle_prop_suffix(jj)
                property_type = jj["type"]
                if not suffix:
                    continue
                if do_refine:
                    refine_init_suffix = jj['init_from_suffix']
                    refine_init_name_list.append(property_type + "_" + refine_init_suffix)
                path_to_prop = os.path.join(ii, property_type + "_" + suffix)
                backup_path(path_to_prop)

    """copy necessary files and directories into temp upload directory"""
    copy_all_other_files(
        work_dir, upload_dir,
        exclude_files=["all_result.json"],
        include_dirs=list(include_dirs)
    )
    for ii in conf_dirs:
        build_conf_path = os.path.join(upload_dir, ii)
        os.makedirs(build_conf_path, exist_ok=True)
        copy_poscar_path = os.path.abspath(os.path.join(ii, "POSCAR"))
        copy_stru_path = os.path.abspath(os.path.join(ii, "STRU"))
        if os.path.isfile(copy_poscar_path):
            target_poscar_path = os.path.join(build_conf_path, "POSCAR")
            shutil.copy(copy_poscar_path, target_poscar_path)
        if os.path.isfile(copy_stru_path):
            target_stru_path = os.path.join(build_conf_path, "STRU")
            shutil.copy(copy_stru_path, target_stru_path)
        if flow_type == "inference":
            if os.path.isdir(build_conf_path):
                shutil.rmtree(build_conf_path)
                #os.remove(build_conf_path)
            shutil.copytree(ii,build_conf_path)
        if flow_type == 'props':
            copy_relaxation_path = os.path.abspath(os.path.join(ii, "relaxation"))
            target_relaxation_path = os.path.join(build_conf_path, "relaxation")
            shutil.copytree(copy_relaxation_path, target_relaxation_path)
            # copy refine from init path to upload dir
            if refine_init_name_list:
                for jj in refine_init_name_list:
                    copy_init_path = os.path.abspath(os.path.join(ii, jj))
                    assert os.path.exists(copy_init_path), f'refine from init path {copy_init_path} does not exist!'
                    target_init_path = os.path.join(build_conf_path, jj)
                    shutil.copytree(copy_init_path, target_init_path)

    os.chdir(cwd)


def submit(
        flow,
        flow_type,
        work_dir,
        relax_param,
        props_param,
        wf_config,
        conf=config,
        s3_conf=s3_config,
        is_sub=False,
        labels=None,
):
    if is_sub:
        # reset dflow global config for sub-processes
        logging.info(msg=f'Sub-process working on: {work_dir}')
        config.update(conf)
        s3_config.update(s3_conf)
        logging.basicConfig(level=logging.INFO)
    else:
        logging.info(msg=f'Working on: {work_dir}')
        
    print(props_param)

    with tempfile.TemporaryDirectory() as tmp_dir:
        logging.debug(msg=f'Temporary upload directory:{tmp_dir}')
        pack_upload_dir(
            work_dir=work_dir,
            upload_dir=tmp_dir,
            relax_param=relax_param,
            prop_param=props_param,
            flow_type=flow_type
        )

        flow_id = None
        flow_name = wf_config.flow_name
        submit_only = wf_config.submit_only
        if flow_type == 'relax':
            flow_id = flow.submit_relax(
                upload_path=tmp_dir,
                download_path=work_dir,
                relax_parameter=relax_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif flow_type == 'props':
            flow_id = flow.submit_props(
                upload_path=tmp_dir,
                download_path=work_dir,
                props_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif flow_type == 'joint':
            flow_id = flow.submit_joint(
                upload_path=tmp_dir,
                download_path=work_dir,
                props_parameter=props_param,
                relax_parameter=relax_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )
        elif flow_type == 'inference':
            flow_id = flow.submit_inference(
                upload_path=tmp_dir,
                download_path=work_dir,
                infer_parameter=props_param,
                submit_only=submit_only,
                name=flow_name,
                labels=labels
            )

    #if not submit_only:
    #    # auto archive results
    #    print(f'Archiving results of workflow (ID: {flow_id}) into {wf_config.database_type}...')
    #    archive_workdir(relax_param, props_param, wf_config, work_dir, flow_type)




def submit_workflow(
        parameter,
        config_dict,
        work_dir,
        flow_type,
        is_debug=False,
        labels=None
):
    #try:
    #    config_dict = loadfn(config_file)
    #except FileNotFoundError:
    #    raise FileNotFoundError(
    #        'Please prepare global.json under current work direction '
    #        'or use optional argument: -c to indicate a specific json file.'
    #    )
    # config dflow_config and s3_config
    wf_config = Config(**config_dict)
    wf_config.config_dflow(wf_config.dflow_config_dict)
    wf_config.config_bohrium(wf_config.bohrium_config_dict)
    wf_config.config_s3(wf_config.dflow_s3_config_dict)
    # set pre-defined dflow debug mode settings
    if is_debug:
        tmp_work_dir = tempfile.TemporaryDirectory()
        config["mode"] = "debug"
        config["debug_workdir"] = config_dict.get("debug_workdir", tmp_work_dir.name)
        s3_config["storage_client"] = None

    print(wf_config.basic_config_dict)
    # judge basic flow info from user indicated parameter files
    if flow_type=="inference":
        make_image=""
        run_op=DPValidate
        run_image = wf_config.basic_config_dict[f"inference_image_name"]
        #if not run_image:
        #    run_image = "registry.dp.tech/dptech/deepmd-kit:2024Q1-d23cf3e"
        run_command=""
        calculator=""
        relax_param={}
        props_param=parameter
    else:
        (run_op, calculator, flow_type,
            relax_param, props_param) = judge_flow(parameter, flow_type)
        print(f'Running calculation via {calculator}')
        make_image = wf_config.basic_config_dict["apex_image_name"]
        run_image = wf_config.basic_config_dict[f"{calculator}_image_name"]
        if not run_image:
            run_image = wf_config.basic_config_dict["run_image_name"]
        run_command = wf_config.basic_config_dict[f"{calculator}_run_command"]
        if not run_command:
            run_command = wf_config.basic_config_dict["run_command"]
    post_image = make_image
    group_size = wf_config.basic_config_dict["group_size"]
    pool_size = wf_config.basic_config_dict["pool_size"]
    executor = wf_config.get_executor(wf_config.dispatcher_config_dict)
    upload_python_packages = wf_config.basic_config_dict["upload_python_packages"]
    upload_python_packages.extend(list(apex.__path__))
    upload_python_packages.extend(list(fpop.__path__))
    upload_python_packages.extend(list(dpdata.__path__))
    upload_python_packages.extend(list(ssb.__path__))
    
    print(f'Submitting {flow_type} workflow...')
    flow = FlowGenerator(
        make_image=make_image,
        run_image=run_image,
        post_image=post_image,
        run_command=run_command,
        calculator=calculator,
        props_make_op=PropsMake,
        props_post_op=PropsPost,
        run_op=run_op,
        group_size=group_size,
        pool_size=pool_size,
        executor=executor,
        upload_python_packages=upload_python_packages
    )
    # submit the workflows
    work_dir_list = []
    for ii in work_dir:
        glob_list = glob.glob(os.path.abspath(ii))
        work_dir_list.extend(glob_list)
    print(work_dir_list)
    if len(work_dir_list) > 1:
        n_processes = len(work_dir_list)
        pool = Pool(processes=n_processes)
        print(f'submitting via {n_processes} processes...')
        for ii in work_dir_list:
            res = pool.apply_async(
                submit,
                (flow, flow_type, ii, relax_param, props_param, config, s3_config, labels)
            )
        pool.close()
        pool.join()
    elif len(work_dir_list) == 1:
        print(relax_param)
        submit(flow, 
               flow_type, 
               work_dir_list[0], 
               relax_param, 
               props_param, 
               wf_config,
               labels=labels
               )
    else:
        raise RuntimeError('Empty work directory indicated, please check your argument')

    print('Completed!')
