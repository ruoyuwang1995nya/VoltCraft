import glob
import os
from multiprocessing import Pool
from ..core.property.MSD import MSD

from apex.core.calculator.calculator import make_calculator
from apex.core.property.Elastic import Elastic
from apex.core.property.EOS import EOS
from apex.core.property.Gamma import Gamma
from apex.core.property.Interstitial import Interstitial
from apex.core.lib.utils import create_path
from apex.core.lib.util import collect_task
from apex.core.lib.dispatcher import make_submission
from apex.core.property.Surface import Surface
from apex.core.property.Vacancy import Vacancy
from apex.core.property.Phonon import Phonon
from apex.utils import sepline, get_task_type
from dflow.python import upload_packages
upload_packages.append(__file__)

lammps_task_type = ["deepmd", "meam", "eam_fs", "eam_alloy"]


def make_property_instance(parameters, inter_param):
    """
    Make an instance of Property
    """
    prop_type = parameters["type"]
    if prop_type == "eos":
        return EOS(parameters, inter_param)
    elif prop_type == "elastic":
        return Elastic(parameters, inter_param)
    elif prop_type == "vacancy":
        return Vacancy(parameters, inter_param)
    elif prop_type == "interstitial":
        return Interstitial(parameters, inter_param)
    elif prop_type == "surface":
        return Surface(parameters, inter_param)
    elif prop_type == "gamma":
        return Gamma(parameters, inter_param)
    elif prop_type == "phonon":
        return Phonon(parameters, inter_param)
    elif prop_type == "msd":
        return MSD(parameters, inter_param)
    else:
        raise RuntimeError(f"unknown dflowautotest type {prop_type}")

