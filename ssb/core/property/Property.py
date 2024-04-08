import glob
import json
import os
from abc import ABC, abstractmethod

from monty.serialization import dumpfn

from ssb.core.calculator.calculator import make_calculator
from dflow.python import upload_packages
upload_packages.append(__file__)


class Property(ABC):
    @abstractmethod
    def __init__(self, parameter):
        """
        Constructor

        Parameters
        ----------
        parameter : dict
            A dict that defines the apex.
        """
        pass

    @abstractmethod
    def make_confs(self, path_to_work, path_to_equi, refine=False):
        """
        Make configurations needed to compute the apex.
        The tasks directory will be named as path_to_work/task.xxxxxx
        IMPORTANT: handel the case when the directory exists.

        Parameters
        ----------
        path_to_work : str
            The path where the tasks for the apex are located
        path_to_equi : str
            -refine == False: The path to the directory that equilibrated the configuration.
            -refine == True: The path to the directory that has apex confs.
        refine : str
            To refine existing apex confs or generate apex confs from a equilibrated conf

        Returns
        -------
        task_list: list of str
            The list of task directories.
        """
        pass

    @abstractmethod
    def post_process(self, task_list):
        """
        post_process the KPOINTS file in elastic.
        """
        pass

    @property
    @abstractmethod
    def task_type(self):
        """
        Return the type of each computational task, for example, 'relaxation', 'static'....
        """
        pass

    @property
    @abstractmethod
    def task_param(self):
        """
        Return the parameter of each computational task, for example, {'ediffg': 1e-4}
        """
        pass
    
    @abstractmethod
    def compute(self, output_file, print_file, path_to_work):
        """
        Postprocess the finished tasks to compute the apex.
        Output the result to a json database

        Parameters
        ----------
        output_file:
            The file to output the apex in json format
        print_file:
            The file to output the apex in txt format
        path_to_work:
            The working directory where the computational tasks locate.
        """
        pass
        # os.chdir(cwd)

    @abstractmethod
    def _compute_lower(self, output_file, all_tasks, all_res):
        """
        Compute the apex.

        Parameters
        ----------
        output_file:
            The file to output the apex
        all_tasks : list of str
            The list of directories to the tasks
        all_res : list of str
            The list of results
        Returns:
        -------
        res_data : dist
            The dict storing the result of the apex
        ptr_data : str
            The result printed in string format
        """
        pass
