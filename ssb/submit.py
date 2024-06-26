import glob
import shutil
import os.path
import tempfile
import logging
from multiprocessing import Pool
from dflow import config, s3_config
from monty.serialization import loadfn
import fpop, dpdata, apex #phonolammps
from apex.config import Config
from apex.flow import FlowGenerator
from apex.submit import judge_flow, submit
import ssb
from .op.property_ops import PropsMake, PropsPost
from .op.eval_ops import direct_inference
import json
import logging

from importlib import import_module
from dflow import (InputArtifact, InputParameter, OutputParameter, S3Artifact,
                   Step, Steps, Workflow, argo_enumerate, if_expression,
                   upload_artifact)
from dflow.plugins.datasets import DatasetsArtifact
from dflow.plugins.dispatcher import DispatcherExecutor, update_dict
from dflow.python import PythonOPTemplate, Slices, upload_packages, OP, Artifact
from pathlib import Path
import shutil

def get_artifact(urn, name="data", detect_systems=False):
    if urn is None:
        return None
    elif isinstance(urn, str) and urn.startswith("oss://"):
        return S3Artifact(key=urn[6:])
    elif isinstance(urn, str) and urn.startswith("launching+datasets://"):
        return DatasetsArtifact.from_urn(urn)
    else:
        if detect_systems:
            path = []
            for ds in urn if isinstance(urn, list) else [urn]:
                for f in glob.glob(os.path.join(ds, "**/type.raw"), recursive=True):
                    path.append(os.path.dirname(f))
        else:
            path = urn
        artifact = upload_artifact(path)
        if hasattr(artifact, "key"):
            logging.info("%s uploaded to %s" % (name, artifact.key))
        return artifact

def import_func(s : str):
    fields = s.split(".")
    if fields[0] == __name__ or fields[0] == "":
        fields[0] = ""
        mod = import_module(".".join(fields[:-1]), package=__name__)
    else:
        mod = import_module(".".join(fields[:-1]))
    return getattr(mod, fields[-1])

def submit_apexBased_wf(
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

    # judge basic flow info from user indicated parameter files
    (run_op, calculator, flow_type,
     relax_param, props_param) = judge_flow(parameter, flow_type)
    print(f'Running calculation via {calculator}')
    print(f'Submitting {flow_type} workflow...')
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
    executor = wf_infer_config.get_executor(wf_config.dispatcher_config_dict)
    upload_python_packages = wf_config.basic_config_dict["upload_python_packages"]
    upload_python_packages.extend(list(apex.__path__))
    upload_python_packages.extend(list(fpop.__path__))
    upload_python_packages.extend(list(dpdata.__path__))
    #upload_python_packages.extend(list(phonolammps.__path__))
    upload_python_packages.extend(list(ssb.__path__))

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

def submit_modelEval_wf(infer_config, config_dict):

    wf_name = infer_config.get("name", "direct-inference")
    datasets = infer_config.get("datasets", None)
    model = infer_config.get("model", None)
    type_map = infer_config.get("type_map", None)
    if not datasets or not model:
        raise ValueError("Both datasets and model must be specified in infer_config")

    # Assuming get_artifact is defined elsewhere
    dataset_artifact = get_artifact(datasets, "datasets")
    model_artifact = get_artifact(model, "model")

    upload_python_packages = []
    upload_python_packages.extend(list(apex.__path__))
    upload_python_packages.extend(list(ssb.__path__))
    infer_executor = config_dict["executor"]    
    executor = DispatcherExecutor(**infer_executor)
    infer_template = PythonOPTemplate(
        direct_inference, 
        image="registry.dp.tech/dptech/deepmd-kit:2024Q1-d23cf3e",
        python_packages=upload_python_packages
    )
    step = Step(
        name="direct-inference",
        template=infer_template,
        parameters={
            "type_map": type_map,
            "msg": "Starting Inference Process"},
        executor=executor,
        artifacts={
            "datasets": dataset_artifact,
            "model": model_artifact
        }
    )

    wf = Workflow(name=wf_name)
    wf.add(step)
    wf.submit()



def submit_workflow(
        parameter,
        config_file,
        work_dir,
        flow_type,
        is_debug=False,
        labels=None
):
    '''try:
        config_dict = loadfn(config_file)
    except FileNotFoundError:
        raise FileNotFoundError(
            'Please prepare global.json under current work direction '
            'or use optional argument: -c to indicate a specific json file.'
        )'''
    try:
        params_dict = loadfn(parameter[0])
        task_type = list(params_dict.keys())[0]
    except FileNotFoundError:
        raise FileNotFoundError(
            """Please prepare json files with parameters under current work direction
            and use sub-argument to appoint it."""
        )

    
    ## submit model evaluation
    if task_type == "direct_inference":
        infer_config = params_dict[task_type]
        submit_modelEval_wf(
            infer_config,
            config_dict
    ) 

    ## submit apex-like wf, e.g. properties calculation    
    else:
        submit_apexBased_wf(
            parameter,
            config_file,
            work_dir,
            flow_type,
            is_debug=False,
            labels=None
    )