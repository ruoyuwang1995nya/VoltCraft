#!/usr/bin/env python3
import os
import random
import subprocess as sp
import sys

import dpdata
from dpdata.periodic_table import Element
from packaging.version import Version
from apex.core.lib import util
from apex.core.calculator.lib.lammps_utils import element_list
from abc import ABC, abstractmethod
from typing import List,Union,Dict
import logging
from dflow.python import upload_packages
upload_packages.append(__file__)

    
  
def make_lammps_property(
    conf, 
    type_map, 
    interaction, 
    inter_param, 
    task_type, 
    task_param
):
    if task_type=="msd":
        return make_lammps_msd(conf, 
                type_map, 
                interaction, 
                inter_param, 
                task_param)
 

def make_lammps_msd(
    conf, 
    type_map, 
    interaction, 
    inter_param, 
    task_param
):
    """
    make lammps input for standard property calculation
    """
    
    type_map_list = element_list(type_map)
    cal_setting=task_param.get("cal_setting",{})
    equi_setting=cal_setting.get("equi_setting",{})
    prop_setting=cal_setting.get("prop_setting",{})
    #if task_param[]

    
    ret = ""
    ret += "clear\n"
    ret += "units 	metal\n"
    ret += "dimension	3\n"
    ret += "boundary	p p p\n"
    ret += "atom_style	atomic\n"
    ret += "box         tilt large\n"
    # variables
    ret += "variable T equal %d\n" % (task_param["cal_temperature"])
    # general settings
    ret += "read_data   %s\n" % conf
    for ii in range(len(type_map)):
        ret += "mass            %d %.3f\n" % (ii + 1, Element(type_map_list[ii]).mass)
    ret += "neigh_modify    every 1 delay 0 check no\n"
    ret += interaction(inter_param)
    # grouping atoms
    for ii in range(len(type_map)):
        ret += "group  %s type %d\n" % (type_map_list[ii],ii + 1)
    
    
    # initial velocity
    ret += "velocity  all create $T 33456 mom yes dist gaussian\n"
    # equilibration: npt
    ret += "fix 1 all npt temp $T $T 0.2 iso 1 1 2\n"
    ret += "thermo_style custom step pe ke etotal press lx ly lz vol density\n"
    ret += "thermo %d\n" %equi_setting.get("thermo-step",1000)
    ret += "run %d\n" %equi_setting.get("run-step",10000)
    ret += "unfix 1\n"
    ## production run
    # assign compute to each atom
    c_msd=""
    for ii in range(len(type_map)):
        ret += "compute  msd%s  %s msd\n" % (ii+1, type_map_list[ii])
        c_msd+="c_msd%s[4] "%(ii+1)
    msd_step=prop_setting.get("msd_step",10)
    ret += "fix 2 all ave/time %d 1 %d %s file msd.out\n"%(msd_step,msd_step,c_msd)
    ret += "fix 1 all nvt temp $T $T 100.0\n"
    ret += "thermo_style custom step time temp ke etotal press density\n"
    ret += "thermo %d\n"%prop_setting.get("thermo-step",1000)
    ret += "run %d\n"%prop_setting.get("run-step",10000)
    return ret
