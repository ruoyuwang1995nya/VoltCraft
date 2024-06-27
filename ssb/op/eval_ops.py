import math
import os
import random
import shutil
import glob
from pathlib import Path
from typing import List, Optional, Tuple
import json
import dpdata
import numpy as np
from dflow.python import OP, OPIO, Artifact, OPIOSign, Parameter


class DPValidate(OP):
    
    def __init__(self):
        pass
    
    @classmethod
    def get_input_sign(cls):
        return OPIOSign(
            {
                #"valid_systems": Artifact(List[Path]),
                "input": Artifact(Path),
                "parameter": Parameter(dict)
            }
        )

    @classmethod
    def get_output_sign(cls):
        return OPIOSign(
            {
                "results": Artifact(Path),
            }
        )

    def load_model(self, model: Path):
        self.model = model
        from deepmd.infer import DeepPot
        self.dp = DeepPot(model)

    def evaluate(self,
                 coord: np.ndarray,
                 cell: Optional[np.ndarray],
                 atype: List[int]
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        coord = coord.reshape([1, -1])
        if cell is not None:
            cell = cell.reshape([1, -1])
        e, f, v = self.dp.eval(coord, cell, atype)
        return e[0], f[0], v[0].reshape([3, 3])

    def validate(self, systems, type_map):
        print(systems, type_map)
        rmse_f = []
        rmse_e = []
        rmse_v = []
        natoms = []
        for sys in systems:
            mixed_type = len(list(sys.glob("*/real_atom_types.npy"))) > 0
            d = dpdata.MultiSystems()
            if (mixed_type):
                d.load_systems_from_file(sys, fmt="deepmd/npy/mixed")
            else:
                k = dpdata.LabeledSystem(sys, fmt="deepmd/npy")
                d.append(k)
            for k in d:
                rmse_f_sys = []
                rmse_e_sys = []
                rmse_v_sys = []
                natoms_sys = []
                for i in range(len(k)):
                    cell = k[i].data["cells"][0]
                    if k[i].nopbc:
                        cell = None
                    coord = k[i].data["coords"][0]
                    force0 = k[i].data["forces"][0]
                    energy0 = k[i].data["energies"][0]
                    virial0 = k[i].data["virials"][0] if "virials" in k[i].data else None
                    ori_atype = k[i].data["atom_types"]
                    anames = k[i].data["atom_names"]
                    atype = np.array([type_map.index(anames[j]) for j in ori_atype])
                    e, f, v = self.evaluate(coord, cell, atype)

                    lx = 0
                    for j in range(force0.shape[0]):
                        lx += (force0[j][0] - f[j][0]) ** 2 + \
                              (force0[j][1] - f[j][1]) ** 2 + \
                              (force0[j][2] - f[j][2]) ** 2
                    err_f = (lx / force0.shape[0] / 3) ** 0.5
                    err_e = abs(energy0 - e) / force0.shape[0]
                    err_v = np.sqrt(np.average((virial0 - v) ** 2)) / force0.shape[0] if virial0 is not None else None
                    print("System: %s frame: %s rmse_e: %s rmse_f: %s rmse_v: %s" % (sys, i, err_e, err_f, err_v))
                    rmse_f_sys.append(err_f)
                    rmse_e_sys.append(err_e)
                    if err_v is not None:
                        rmse_v_sys.append(err_v)
                    natoms_sys.append(force0.shape[0])
                rmse_f.append(rmse_f_sys)
                rmse_e.append(rmse_e_sys)
                if len(rmse_v_sys) > 0:
                    rmse_v.append(rmse_v_sys)
                natoms.append(natoms_sys)
        return rmse_f, rmse_e, rmse_v if len(rmse_v) > 0 else None, natoms

    @OP.exec_sign_check
    def execute(self, op_in: OPIO) -> OPIO:
        #print("OK")
        input_work_dir = op_in["input"]
        cwd= Path.cwd()
        os.chdir(input_work_dir)
        print(os.listdir('./'))
        parameter=op_in["parameter"]
        print(parameter)
        path_to_model=parameter["interaction"].get("model")
        path_to_sys=parameter.get("structures")#["datasets"]
        type_map=parameter["direct_inference"].get("type_map")#]
        # access model
        abs_path_to_model = input_work_dir / path_to_model
        self.load_model(abs_path_to_model)
        results={}
        print(path_to_sys)
        #for sys in path_to_sys:
        path_to_sys_all=[]
        for sys in path_to_sys:
            path_to_sys_all.extend(glob.glob(sys))
        abs_path_to_sys = [input_work_dir / sys for sys in path_to_sys_all]
        #name=Path(abs_path_to_sys).name
        rmse_f, rmse_e, rmse_v, natoms = self.validate(abs_path_to_sys, type_map)
        na = sum([sum(i) for i in natoms])
        nf = sum([len(i) for i in natoms])
        rmse_f = np.sqrt(sum([sum([i ** 2 * j for i, j in zip(r, n)]) for r, n in zip(rmse_f, natoms)]) / na)
        rmse_e = np.sqrt(sum([sum([i ** 2 for i in r]) for r in rmse_e]) / nf)
        rmse_v = float(np.sqrt(np.average(np.concatenate(rmse_v) ** 2))) if rmse_v is not None else None
        print(rmse_e, rmse_f, rmse_v)
        results = {"rmse_f": float(rmse_f), "rmse_e": float(rmse_e), "rmse_v": rmse_v}
        os.chdir(cwd)
        with open("infer_result.json",'w') as f:
            json.dump(results,f,indent=4)
        op_out=OPIO({
            "results": Path("./infer_result.json")
            }
            )
        
        return op_out#OPIO({"results": {"status": 0}})