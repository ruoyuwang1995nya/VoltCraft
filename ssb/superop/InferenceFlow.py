import os
from pathlib import (
    Path,
)
from typing import (
    List,
    Optional,
    Type,
)
from dflow import (
    InputArtifact,
    InputParameter,
    Inputs,
    OutputArtifact,
    OutputParameter,
    Outputs,
    Step,
    Steps,
    Workflow,
    argo_len,
    argo_range,
    upload_artifact,
)
from dflow.python import (
    OP,
    PythonOPTemplate,
    Slices,
)
from dflow.plugins.dispatcher import DispatcherExecutor


class InferenceFlow(Steps):

    def __init__(
        self,
        name: str,
        infer_op: Type[OP],
        infer_image: str,
        infer_command: Optional[str] = None,
        group_size: Optional[int] = None,
        pool_size: Optional[int] = None,
        executor: Optional[DispatcherExecutor] = None,
        upload_python_packages: Optional[List[os.PathLike]] = None,
    ):
        self._input_parameters = {
            "flow_id": InputParameter(type=str, value=""),
            "parameter": InputParameter(type=dict)
        }
        self._input_artifacts = {
            "input_work_path": InputArtifact(type=Path),
        }
        self._output_parameters = {
            #"results":OutputParameter(type=dict)
        }
        self._output_artifacts = {
            "results":OutputArtifact(type=Path)
            
        }

        super().__init__(
            name=name,
            inputs=Inputs(
                parameters=self._input_parameters,
                artifacts=self._input_artifacts
            ),
            outputs=Outputs(
                parameters=self._output_parameters,
                artifacts=self._output_artifacts
            ),
        )

        self._keys = ["infer"]
        self.step_keys = {}
        key = "infer"
        self.step_keys[key] = '--'.join(
            [str(self.inputs.parameters["flow_id"]), 'infer', key]
        )
        self._build(
            name,
            infer_op,
            infer_image,
            infer_command,
            group_size,
            pool_size,
            executor,
            upload_python_packages
        )

    @property
    def input_parameters(self):
        return self._input_parameters

    @property
    def input_artifacts(self):
        return self._input_artifacts

    @property
    def output_parameters(self):
        return self._output_parameters

    @property
    def output_artifacts(self):
        return self._output_artifacts

    @property
    def keys(self):
        return self._keys

    def _build(
        self,
        name: str,
        infer_op: Type[OP],
        infer_image: str,
        run_command: Optional[str] = None,
        group_size: Optional[int] = None,
        pool_size: Optional[int] = None,
        executor: Optional[DispatcherExecutor] = None,
        upload_python_packages: Optional[List[os.PathLike]] = None,
    ):
        infer = Step(
            name=name,
            template=PythonOPTemplate(infer_op,
                                      image=infer_image,
                                      python_packages=upload_python_packages,
                                      command=["python3"]),
            artifacts={
                "input": self.inputs.artifacts["input_work_path"]
                },
            parameters={
                "parameter": self.inputs.parameters["parameter"]
                },
            key=self.step_keys["infer"]
        )
        self.add(infer)
        self.outputs.artifacts["results"]._from = infer.outputs.artifacts["results"]