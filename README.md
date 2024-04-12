# VoltCraft: Battery simulation workflow automation
[VoltCraft](https://github.com/ruoyuwang1995ucas/LAM-SSB) aims for easy automation of battery simulation, which utilized advanced machine-learning techniques such as DeePMD and DPA. VoltCraft is currently an extension of the general [APEX](https://github.com/deepmodeling/APEX) workflow, though a standalone version dedicated to battery simulation is incoming.

## Table of Contents

- [VoltCraft: Battery simulation workflow automation](#voltcraft-battery-simulation-workflow-automation)

  - [1. Overview](#1-overview)
  - [2. Installation](#2-installation)
  - [3. Quick Start](#3-quick-start)
  - [4. User Guide](#4-user-guide)


## 1. Overview
VoltCraft reorients the versatile workflow design of the APEX package to battery property simulation, with particular emphasis on **solid electrolyte**. By incorporating our extensive know-how in battery simulation, automation of complex workflow, such as the calculation of elastic modulus, diffusion coefficient and ionic conductivity, can be conveniently realized. 

Below is a schematic showing the basic structure of VoltCraft package.
 <div>
    <img src="./docs/images/schematic.png" alt="Fig1" style="zoom: 35%;">
    <p style='font-size:1.0rem; font-weight:none'>Figure 1. Workflow design of VoltCraft at current stage.</p>
</div>

At current stage, VoltCraft implements modules aiming for atomic simulation of solid electrolyte at finite temperature. Critical dynamical parameters of solid electrolyte, e.g., [mean square displacement](https://en.wikipedia.org/wiki/Mean_squared_displacement) (MSD), diffusion coefficient and ionic conductivity, can be derived from the simulation trajectory.  Algorithms for more dynamic properties, such as ionic hopping barrier, are set to arrive in the near future.

## 2. Installation
VoltCraft can be built and installed form the source. Clone the package firstly by
```shell
git clone https://github.com/ruoyuwang1995ucas/VoltCraft.git
```

then install by
```shell
cd VoltCraft
pip install .
```

## 3. Quick Start
VoltCraft can be activated either from CLI or through python API. For new users, we recommend the CLI method. Below are a few examples on the usage of VoltCraft package.

### 3.1 Diffusion Coefficient
In this example, we are going to show how to calculate the diffusion coefficient of Lithium ions in LPSCl solid electrolyte.First navigate to LPSCl work directory, suppose the work directory is at the source
```shell
cd examples/LPSCl
```

You can check the input directory tree. It contains an initial POSCAR in the confs/conf-1 directory. Multiple configurations can be specified in the parameter file.

Then, to run the workflow you need to configure the [dflow](https://github.com/dptech-corp/dflow) setting, which wraps the ARGO python API of Kubernetes. You can run the task either on the [Bohrium](https://bohrium.dp.tech/home) platform or locally in the debug mode. An example server config file looks like this
```json
{
    "dflow_host": "https://workflows.deepmodeling.com",
    "k8s_api_server": "https://workflows.deepmodeling.com",
    "email": "your email",
    "password": "your password",
    "program_id": 123456,
    "apex_image_name": "registry.dp.tech/dptech/prod-11045/apex-dependency:1.1.0",
    "lammps_image_name": "registry.dp.tech/dptech/dpmd:2.2.8-cuda12.0",
    "group_size": 4,
    "pool_size": 1,
    "run_command": "lmp -in in.lammps",
    "batch_type": "Bohrium",
    "context_type": "Bohrium",
    "scass_type": "c16_m62_1 * NVIDIA T4"
}
```
In this case, we are going to use LAMMPS as the simulation tool.

Next, we are going to calculate the diffusion coefficient $D$ of lithium ion (Li<sup>+</sup>) from the mean square displacement over a certain period of time. The following json file is created to specify the calculation settings:

```json
{
    "structures":    ["confs/conf-1"],
    "interaction": {
        "type":          "deepmd",
        "model":         "frozen_model.pb",
        "deepmd_version":"2.2.8",
        "type_map":      {"Li":0,"B":1,"O":2,"Al":3,"Si":4,"P":5,"S":6,"Cl":7,"Ga":8,"Ge":9,"As":10,"Br":11,"Sn":12,"Sb":13,"I":14}
    },
    "properties": [
        {
         "type":         "msd",
         "skip":         false,
         "using_template": true,
         "temperature": 900,
         "supercell":      [2,2,2],
	      "cal_setting":  {
                "equi_setting":{
                    "thermo-step":100,
                    "run-step":10000
            },
                "prop_setting":{
                    "thermo-step":100,
                    "run-step":10000,
                    "msd_step":100
                }
                    
            }
        }
        ]
}
```
A brief explanation for the input parameters. A built-in template for LAMMPS molecular simulation is used which let users to specify the simulation temperature, cell dimension, simulation steps, *etc*.

We can submit the workflow to Bohrium server by 
```shell
vcraft submit  param_props.json  -f props -c global_bohrium.json -w ./ 
```
If you'd rather run the workflow locally, you can add an additional `-d` argument after the `submit` command. But make sure you have all the neccesary package installed...
```shell
vcraft submit -d param_props.json -f props -c global_bohrium.json -w ./
```

After a few minutes, if nothing goes wrong, the result would be downloaded to your work directory, which is your current directory. The msd of the four ion types: Li, P, S and Cl, are shown below.
 <div>
    <img src="./docs/images/msd.png" alt="Fig1" style="zoom: 35%;">
    <p style='font-size:1.0rem; font-weight:none'>Figure 2. Ionic mean square displacment (MSD) of LPSCl solid electrolyte at 900 K.</p>
</div>

*Note*: this is only for demonstration. The simulation time and cell dimension may not have fully converged. 

You can find the calculated diffusion coefficient (valid in linear regime) at `confs/conf-1/msd_00/result.json`. By some easy data manipulation, you can calculate the ionic conductivity of Li<sup>+</sup> from the Nernst-Einstein relation.

### 3.2 Elastic Modulus
VoltCraft also implements the algorithms to calculate elastic modulus, which is identical to that of APEX package. Here, the elastic modulus of LiBr solid electrolyte would be calculated. An example input file looks like:
```json
{
    "structures":    ["confs/cubic"],
    "interaction": {
        "type":          "deepmd",
        "model":         "frozen_model.pb",
        "deepmd_version":"2.2.8",
        "type_map":       {"Li":0,"B":1,"O":2,"Al":3,"Si":4,"P":5,"S":6,"Cl":7,"Ga":8,"Ge":9,"As":10,"Br":11,"Sn":12,"Sb":13,"I":14}
    },
    "relaxation": {
        "cal_setting":   {"etol":       0,
                        "ftol":     1e-10,
                        "maxiter":   5000,
                        "maximal":  500000}
  },
    "properties": [
  {
    "type":         "elastic",
    "skip":         false,
    "norm_deform":  1e-2,
    "shear_deform": 1e-2,
    "cal_setting":  {"etol": 0,
                    "ftol": 1e-10}
  }
  ]
}
```
Navigate to the `example/LiBr` directory, and submit the workflow
```shell
vcraft submit param_props.json -f joint -c global_bohrium.json -w ./
```
*Note\*: this example includes both lattice relaxation and elastic calculation, so the flow type needs to be specified as `joint`. However, this may be subject to change in the future.*

*Note\*\*: you should copy the `example/LPSCl/frozen_model.pb` to current directory before workflow submission.*

Once the results are collected, the optimized cell parameters, atom coords, virials, *etc.*, are stored at `example/LiBr/confs/cubic/relaxation/relax_task/result.json`. For instance, the relaxed lattice parameter should be `5.44` Angstrom. 

Three types of elastic modulus, i.e., bulk modulus, shear modulus and Young's modulus, are calculated, and the result can be shown by
```shell
cat example/LiBr/confs/cubic/elastic_00/result.out

# Bulk   Modulus BV = 29.34 GPa
# Shear  Modulus GV = 18.63 GPa
# Youngs Modulus EV = 46.12 GPa
# Poission Ratio uV = 0.24
```


## 4. User Guide
Users are refered to [APEX](https://github.com/deepmodeling/APEX) user manual for an extensive explanation of the workflow structure. Currently [VoltCraft](https://github.com/ruoyuwang1995ucas/LAM-SSB) keeps all the functionalities of the original [APEX](https://github.com/deepmodeling/APEX).



