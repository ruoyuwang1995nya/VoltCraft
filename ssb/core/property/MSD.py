import glob
import json
import logging
import os
import re
from pathlib import Path
import dpdata
import numpy as np
from monty.serialization import dumpfn, loadfn

from apex.core.calculator.lib import abacus_utils
from apex.core.calculator.lib import vasp_utils
from apex.core.calculator.lib import abacus_scf
from apex.core.refine import make_refine
from apex.core.reproduce import make_repro, post_repro
from ssb.core.property.Property import Property

from dflow.python import upload_packages
upload_packages.append(__file__)


class MSD(Property):
    def __init__(self, parameter, inter_param=None):
        parameter["reproduce"] = parameter.get("reproduce", False)
        self.reprod = parameter["reproduce"]
        if not self.reprod:
            if not ("init_from_suffix" in parameter and "output_suffix" in parameter):
                default_supercell = [1, 1, 1]
                default_temperature = [300] # in Kelvin
                parameter["supercell"] = parameter.get("supercell", default_supercell)
                self.supercell = parameter["supercell"]
                parameter["temperature"] = parameter.get("temperature", default_temperature)
                self.temperature = parameter["temperature"]
            parameter["cal_type"] = parameter.get("cal_type", "static")
            self.cal_type = parameter["cal_type"]
            self.cal_setting=parameter["cal_setting"]
        
        # to be completed... 
        
        self.parameter = parameter
        self.inter_param = inter_param if inter_param != None else {"type": "vasp"}
        pass

    def make_confs(self, path_to_work, path_to_equi, refine=False):
        """
        Return a list of task directories which includes POSCAR
        """
        path_to_work = os.path.abspath(path_to_work)
        if os.path.exists(path_to_work):
            #dlog.warning("%s already exists" % path_to_work)
            logging.warning("%s already exists" % path_to_work)
        else:
            os.makedirs(path_to_work)
        path_to_equi = os.path.abspath(path_to_equi)

        if "start_confs_path" in self.parameter and os.path.exists(
            self.parameter["start_confs_path"]
        ):
            init_path_list = glob.glob(
                os.path.join(self.parameter["start_confs_path"], "*")
            )
            struct_init_name_list = []
            for ii in init_path_list:
                struct_init_name_list.append(ii.split("/")[-1])
            struct_output_name = path_to_work.split("/")[-2]
            assert struct_output_name in struct_init_name_list
            path_to_equi = os.path.abspath(
                os.path.join(
                    self.parameter["start_confs_path"],
                    struct_output_name,
                    "relaxation",
                    "relax_task",
                )
            )

        cwd = os.getcwd()
        task_list = []
        # reproduce previous results (provided with input files?)
        if self.reprod:
            print("msd reproduce starts")
            if "init_data_path" not in self.parameter:
                raise RuntimeError("please provide the initial data path to reproduce")
            init_data_path = os.path.abspath(self.parameter["init_data_path"])
            task_list = make_repro(
                self.inter_param,
                init_data_path,
                self.init_from_suffix,
                path_to_work,
                self.parameter.get("reprod_last_frame", True),
            )
            os.chdir(cwd)

        else:
            if refine:
                print("msd refine starts")
                task_list = make_refine(
                    self.parameter["init_from_suffix"],
                    self.parameter["output_suffix"],
                    path_to_work,
                )
                os.chdir(cwd)

                init_from_path = re.sub(
                    self.parameter["output_suffix"][::-1],
                    self.parameter["init_from_suffix"][::-1],
                    path_to_work[::-1],
                    count=1,
                )[::-1]
                task_list_basename = list(map(os.path.basename, task_list))

                for ii in task_list_basename:
                    init_from_task = os.path.join(init_from_path, ii)
                    output_task = os.path.join(path_to_work, ii)
                    os.chdir(output_task)
                    if os.path.isfile("eos.json"):
                        os.remove("eos.json")
                    if os.path.islink("eos.json"):
                        os.remove("eos.json")
                    os.symlink(
                        os.path.relpath(os.path.join(init_from_task, "eos.json")),
                        "eos.json",
                    )
                os.chdir(cwd)

            else:
                print(
                    "gen msd at temperatures "
                    + str(self.temperature)
                    + "K"
                )

                if self.inter_param["type"] == "abacus":
                    equi_contcar = os.path.join(
                        path_to_equi, abacus_utils.final_stru(path_to_equi)
                    )
                else:
                    equi_contcar = os.path.join(path_to_equi, "CONTCAR")

                if not os.path.isfile(equi_contcar):
                    logging.warning("%s does not exist, trying default POSCAR" % equi_contcar)
                    #if 
                    print(path_to_work)
                    equi_contcar = os.path.join(Path(path_to_work).parent,"POSCAR")
                    if not os.path.isfile(equi_contcar):
                        raise RuntimeError(
                        "Can not find %s, please provide with POSCAR" % equi_contcar
                        )


                task_num = 0
                for temp in self.temperature:
                    # this actually has something to do with the "Property.compute()" 
                    # method invoked within the PropsPost OP. Task dir must have the 
                    # form task.%06d
                    output_task = os.path.join(path_to_work, "task.%06d" % task_num)
                    os.makedirs(output_task, exist_ok=True)
                    os.chdir(output_task)
                    if self.inter_param["type"] == "abacus":
                        POSCAR = "STRU"
                        #POSCAR_orig = "STRU.orig"
                    else:
                        POSCAR = "POSCAR"
                        #POSCAR_orig = "POSCAR.orig"

                    for ii in [
                        "INCAR",
                        "POTCAR",
                        POSCAR,
                        "conf.lmp",
                        "in.lammps",
                    ]:
                        if os.path.exists(ii):
                            os.remove(ii)
                    task_list.append(output_task)
                    
                    if self.inter_param["type"] == "abacus":
                        raise NotImplementedError("ABACUS interaction is not implemented yet!")
                    else:
                        supercell=dpdata.System(equi_contcar,fmt="vasp/poscar").replicate(self.supercell)
                        sc_contcar=os.path.join(Path(path_to_work).parent,"SUPERCELL")
                        supercell.to("vasp/poscar",
                                     sc_contcar,
                                     frame_idx=0)
                    os.symlink(os.path.relpath(sc_contcar), POSCAR)
                    msd_params = {"temperature": temp,
                                  "supercell":self.supercell
                                  }
                    dumpfn(msd_params, "msd.json", indent=4)
                    task_num += 1
                os.chdir(cwd)
        return task_list

    def post_process(self, task_list):
        pass

    def task_type(self):
        return self.parameter["type"]

    def task_param(self):
        
        return self.parameter
    def compute(self,output_file, all_tasks, all_res):
        pass

    def _compute_lower(self, output_file, all_tasks, all_res):
        output_file = os.path.abspath(output_file)
        res_data = {}
        ptr_data = "conf_dir: " + os.path.dirname(output_file) + "\n"
        if not self.reprod:
            ptr_data += " VpA(A^3)  EpA(eV)\n"
            for ii in range(len(all_tasks)):
                # vol = self.vol_start + ii * self.vol_step
                temp = loadfn(os.path.join(all_tasks[ii], "msd.json"))["temperature"]
                task_result = loadfn(all_res[ii])
                # do nothing here? 
                

        else:
            if "init_data_path" not in self.parameter:
                raise RuntimeError("please provide the initial data path to reproduce")
            init_data_path = os.path.abspath(self.parameter["init_data_path"])
            res_data, ptr_data = post_repro(
                init_data_path,
                self.parameter["init_from_suffix"],
                all_tasks,
                ptr_data,
                self.parameter.get("reprod_last_frame", True),
            )

        with open(output_file, "w") as fp:
            json.dump(res_data, fp, indent=4)

        return res_data, ptr_data
