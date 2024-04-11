import glob
import json
import logging
import os
import shutil
import re
from pathlib import Path
import dpdata
import numpy as np
import matplotlib
matplotlib.use('pdf')
import matplotlib.pyplot as plt
from monty.serialization import dumpfn, loadfn
from apex.core.property.Property import Property
from apex.core.calculator.lib import abacus_utils
from apex.core.calculator.lib import vasp_utils
from apex.core.calculator.lib import abacus_scf
from apex.core.refine import make_refine
from apex.core.reproduce import make_repro, post_repro
#from ssb.core.property.Property import Property

from dflow.python import upload_packages
upload_packages.append(__file__)


class MSD(Property):
    def __init__(self, parameter, inter_param=None):
        parameter["reproduce"] = parameter.get("reproduce", False)
        self.reprod = parameter["reproduce"]
        if not self.reprod:
            #if not ("init_from_suffix" in parameter and "output_suffix" in parameter):
            default_supercell = [1, 1, 1]
            default_temperature = 300 # in Kelvin
            parameter["supercell"] = parameter.get("supercell", default_supercell)
            self.supercell = parameter["supercell"]
            
            parameter["cal_type"] = parameter.get("cal_type", "static")
            self.cal_type = parameter["cal_type"]
            
            ## if custom in.lammps is used
            self.custom_input=parameter.get("custom_input")
            
            
            ## if template in.lammps is used
            self.using_template=parameter.get("using_template",True)
            #  temperature for template
            parameter["temperature"] = parameter.get("temperature", default_temperature)
            self.temperature = parameter["temperature"]
            
            # cal_setting for template
            parameter["cal_setting"]=parameter.get("cal_setting",{})
            self.cal_setting=parameter["cal_setting"]
            
            ## settings for output format
            parameter["res_setting"]=parameter.get("res_setting",{})
            
        
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
            pass

        cwd = os.getcwd()
        task_list = []
        # reproduce previous results (provided with input files?)
        if self.reprod:
            pass

        else:
            if refine:
                pass

            else:
                print(
                    "Start generating mean square displacement calculation"
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
                task_map=[]
                input_prop=[]
                if self.custom_input\
                    and isinstance(self.custom_input,str):
                    logging.info("Using default user input. Overriding temperature setting")
                    if os.path.isfile(self.custom_input):
                        task_map.append("overridden")
                        input_prop.append(os.path.abspath(self.custom_input))
                    else:
                        raise FileNotFoundError("The input file %s does not exist!"%self.custom_input)
                    
                elif self.custom_input\
                    and isinstance(self.custom_input,list):
                    logging.info("Using default user input. Overriding temperature setting")
                    for id,ipt in enumerate(self.custom_input):
                        if os.path.isfile(ipt):
                            input_prop.append(os.path.abspath(ipt))
                            task_map.append("task.%06d"%id)
                        else:
                            raise FileNotFoundError("The input file %s does not exist!" %ipt)
                    
                elif self.using_template is True:
                    logging.info("Using templated LAMMPS input file!")
                    if isinstance(self.temperature,int):
                        task_map.append(self.temperature)
                        self.parameter["cal_temperature"]=self.temperature
                    elif isinstance(self.temperature,list):
                        task_map.extend(self.temperature)
                        self.parameter["cal_temperature"]=self.temperature
                    else:
                        raise TypeError("Temperature has to be an integer!")
                    
                else:
                    raise RuntimeError("Either use a template or provide a custom in.lammps!")
                
                for temp in task_map:
                    # this actually has something to do with the "Property.compute()" 
                    # method invoked within the PropsPost OP. Task dir must have the 
                    # form task.%06d
                    output_task = os.path.join(path_to_work, "task.%06d" % task_num)
                    os.makedirs(output_task, exist_ok=True)
                    os.chdir(output_task)
                    if self.inter_param["type"] == "abacus":
                        POSCAR = "STRU"
                    else:
                        POSCAR = "POSCAR"
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
                    # if custom_input
                    if len(input_prop)>0:
                        shutil.copy(input_prop[task_num],"in.lammps")
                    
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
        return "msd"#self.parameter["type"]

    def task_param(self):
        return self.parameter
    
    def compute(self,output_file, print_file, path_to_work):
        if skip:=self.parameter["res_setting"].get("skip"):
            if skip is True:
                logging.warning("result proccessing is skipped!")
                return
        logging.info("Processing msd output!")
        path_to_work = os.path.abspath(path_to_work)
        # task directory
        task_dirs = glob.glob(os.path.join(path_to_work, "task.[0-9]*[0-9]"))
        task_dirs.sort()
        # read msd output filename
        res_setting=self.parameter["res_setting"]
        msd_data=res_setting.get("filename","msd.out")
        
        all_res=[]
        for ii in task_dirs:
            task_res={}
            msd_data=os.path.join(ii,msd_data)
            task_res["diffusion_coef"]=__class__.msd2diff(msd_data,res_setting,png_path=ii)
            if self.using_template is True:
                task_res["cal_setting"]=self.cal_setting
            else:
                task_res["cal_setting"]="custom"
            dumpfn(task_res,os.path.join(ii,"result_task.json"),indent=4)
            all_res.append(os.path.join(ii,"result_task.json"))
            
        res, ptr = self._compute_lower(output_file,task_dirs,all_res)
        
        with open(output_file,"w") as fp:
            json.dump(res,fp,indent=4)
                
        with open(print_file,"w") as fp:
            fp.write(ptr)
            
    def _compute_lower(self,output_file, all_tasks, all_res):
        output_file=os.path.abspath(output_file)
        res_data={}
        ptr_data="conf_dir: "+os.path.basename(output_file)+"\n"
        for ii in range(len(all_tasks)):
            task_result=loadfn(all_res[ii])
            res_data[os.path.basename(all_tasks[ii])]=task_result
            ptr_data+=os.path.basename(all_tasks[ii])+":\n"
            ptr_data+=json.dumps(task_result)
        return res_data, ptr_data
    
    @staticmethod
    def msd2diff(
                 msd_data,
                param:dict,
                png_path='./'
                         ):
        if not os.path.isfile(msd_data):
            logging.warning("Invalid msd output filepath!")
            return
        delimiter=param.get("delimiter")
        data = np.loadtxt(msd_data,delimiter=delimiter)
        timestep = data[:, 0]
        dt=param.get("dt",1)
        time = timestep * dt   # input.lammps：t_step= 1fs
        n = data.shape[0]
        n1 = int(n * 0.3)
        n2 = int(n * 0.9)
        ion_list=param.get("ion_list",["ion_%s"%(i+1) for i in range(data.shape[1]-1)])
        msd={}
        diff={}
        diff_cvt=param.get("diff_cvt",1e-5)
        plt.clf()
        for idx,ion in enumerate(ion_list):
            msd[ion] = data[:, idx+1]
            plt.scatter(time, msd[ion], label=ion) # 1fs= 1/1000ps
            slope,residuals = np.polyfit(time[n1:n2], msd[ion][n1:n2], 1)
            plt.plot(time,[slope * t + residuals for t in time],color="gray")
            diff[ion]=slope/6*diff_cvt # convert to m^2/s
        plt.xlabel('timestep(%s)'%param.get("time_unit","fs"))
        plt.ylabel('MSD(%s$^2$)'%param.get("length_unit","Å"))
        plt.title("MSD")
        plt.legend()
        plt.grid()
        plt.savefig(os.path.join(png_path,'msd.png'), dpi=300)
        return diff
