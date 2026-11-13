# vLLM Guide (sample corpus — original summary)

## What is vLLM
vLLM is an open-source library for fast large language model inference and serving. Its central idea is PagedAttention, which manages key-value cache memory in fixed-size blocks inspired by operating-system virtual memory paging. By avoiding the large contiguous reservations that older engines needed, PagedAttention reduces KV cache fragmentation and lets the server batch many more concurrent requests on the same GPU.

## Installing vLLM
You can install vLLM with pip inside a Python environment that matches your CUDA version. The package ships an offline LLM class for batch generation in scripts and an OpenAI-compatible server for online serving. GPU memory is the main constraint: the model weights plus the KV cache must fit in device memory, and the gpu-memory-utilization setting controls what fraction of the GPU the engine may claim.

## Offline batch inference
The offline LLM class loads a model once and generates outputs for a whole list of prompts in a single run. Sampling parameters such as temperature, top-p, and max tokens are passed through a SamplingParams object per request. Offline mode suits evaluation sweeps and dataset generation because throughput is maximised when the engine always has work queued.

## OpenAI-compatible server
Starting the server exposes chat and completion endpoints that mirror the OpenAI API, so existing client code usually only needs a new base URL. Requests stream token by token when the client sets stream to true. Because the server speaks the OpenAI protocol, AgentDesk points its LLM_BASE_URL at a vLLM server and only changes the model name to switch engines.

## Continuous batching
vLLM schedules requests with continuous batching: new requests join the running batch at every decoding step instead of waiting for a whole batch to finish. Finished requests leave immediately and free their KV cache blocks. The result is much higher GPU utilisation and lower latency variance than static batching, especially when prompts and outputs have very different lengths.

## Prefix caching
When many requests share a long common prefix, such as the same system prompt, prefix caching reuses the KV cache blocks computed for that prefix instead of recomputing them. This cuts time to first token for chat workloads and multi-turn conversations. The feature is enabled with the enable-prefix-caching flag and pays off most when prompts share long identical beginnings.

## Quantization
Quantized models store weights in fewer bits, commonly AWQ, GPTQ, or FP8 formats, trading a small amount of accuracy for much lower memory use. An 8-bit or 4-bit checkpoint can fit a model on a smaller GPU or leave more room for KV cache, which increases concurrency. vLLM selects the quantization kernel from the model config, and you pass the quantization method explicitly when the checkpoint does not declare it.

## Key metrics: TTFT and TPOT
Time to first token, or TTFT, measures how long a user waits before generation starts and is dominated by prefill of the prompt. Time per output token, or TPOT, measures the steady-state decoding speed once generation is running. Operators track p50 and p99 values of both, because tail latency under concurrency, not the average, is what users actually feel.

## Tensor parallelism
Models too large for one GPU can be split across devices with tensor parallelism, which shards the weight matrices and synchronises partial results with collectives. You set the number of participating GPUs with tensor-parallel-size. Tensor parallelism adds communication overhead, so it pays off only when a model cannot fit, or cannot serve enough concurrency, on a single device.

## Troubleshooting out of memory
If the server fails with CUDA out of memory, first lower gpu-memory-utilization expectations are not the issue — instead reduce max model length, lower the maximum number of sequences, or move to a quantized checkpoint. Long maximum context lengths reserve large KV cache pools. Checking the startup log's reported KV cache size tells you how much room the engine actually had for requests.
