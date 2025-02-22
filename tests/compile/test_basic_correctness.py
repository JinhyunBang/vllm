from typing import Dict, List, Optional

import pytest

from vllm.compilation.levels import CompilationLevel
from vllm.utils import cuda_device_count_stateless

from ..utils import compare_all_settings


# we cannot afford testing the full Catesian product
# of all models and all levels
@pytest.mark.parametrize(
    "model, model_args, pp_size, tp_size, attn_backend, method, fullgraph",
    [
        ("meta-llama/Llama-3.2-1B", [], 2, 2, "FLASHINFER", "generate", True),
        ("nm-testing/Meta-Llama-3-8B-Instruct-W8A8-Dyn-Per-Token-2048-Samples",
         ["--quantization", "compressed-tensors"
          ], 1, 1, "FLASH_ATTN", "generate", True),
        ("ibm/PowerMoE-3b", [], 1, 2, "FLASH_ATTN", "generate", True),
        # TODO: add multi-modality test for llava
        ("llava-hf/llava-1.5-7b-hf", [], 2, 1, "FLASHINFER", "generate", False)
    ])
def test_compile_correctness(model, model_args, pp_size, tp_size, attn_backend,
                             method, fullgraph):
    # this test is run under multiple suits, with different GPUs.
    # make sure we only run the test with correct CUDA devices.
    # don't use "<", as it will duplicate the tests.
    if cuda_device_count_stateless() != pp_size * tp_size:
        pytest.skip("Not correct CUDA devices for the test.")
    import os
    os.environ["VLLM_ATTENTION_BACKEND"] = attn_backend
    all_args = [["--enforce-eager"] + model_args + ["-pp", str(pp_size)] +
                ["-tp", str(tp_size)]] * 3
    # don't test VLLM_TORCH_COMPILE_LEVEL == 3 case
    # inductor will change the output, so we cannot compare them.
    all_envs: List[Optional[Dict[str, str]]] = []
    for level in [
            CompilationLevel.NO_COMPILATION,
            CompilationLevel.DYNAMO_AS_IS,
            CompilationLevel.DYNAMO_ONCE,
    ]:
        all_envs.append({"VLLM_TORCH_COMPILE_LEVEL": str(level)})
        if level != CompilationLevel.DYNAMO_ONCE and not fullgraph:
            # "DYNAMO_ONCE" will always use fullgraph
            all_envs[-1][
                "VLLM_TEST_DYNAMO_FULLGRAPH_CAPTURE"] = "0"  # type: ignore

    compare_all_settings(model, all_args, all_envs, method=method)
