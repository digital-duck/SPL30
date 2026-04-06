Liquid AI's Python integration focuses on deploying Liquid Foundation Models (LFMs) for high-efficiency, on-device, and edge-native applications. While Liquid AI does not currently offer a centralized hosted API of its own, they provide tools for local deployment and access through third-party providers. [1, 2, 3]  
Core Integration Methods 

• Liquid AI SDK (LEAP SDK): Use the LEAP SDK to deploy LFMs natively on edge devices like laptops and embedded systems. It is designed for low-latency (&lt;100ms) performance without cloud dependencies. 
• Third-Party API Providers: For standard cloud API access, Liquid AI models (like LFM2-24B-A2B) are available on OpenRouter and Puter. These providers offer OpenAI-compatible endpoints that can be called using the standard  Python library. 
• Local Inference Engines: 

	• Ollama: Liquid models are supported in Ollama (v0.17.1-rc0 or later) for local serving with an  OpenAI-compatible API 
. 
	• llama.cpp: Python bindings for  support LFM2 models for CPU-efficient inference. 
	• vLLM: Recommended for high-throughput production deployments on GPU-enabled environments. [1, 4, 5, 6, 7, 8]  

Official Python Packages 

| Package [9, 10, 11, 12] | Purpose  |
| --- | --- |
| — | Official client for managing API keys and environment variables on the Liquid platform.  |
| — | Multiplatform SDK for edge-native deployment of LFMs.  |
| — | End-to-end Python library for speech-to-speech foundation models.  |

Getting Started 

1. Obtain a Key: Access the Liquid Labs playground for free testing or use third-party providers for paid production tiers. 
2. Install the Client: 
3. Explore Tutorials: The Liquid AI Cookbook on GitHub contains end-to-end Python tutorials for building AI agents and mobile-ready applications. [2, 13, 14, 15, 16]  

AI responses may include mistakes.

[1] https://www.liquid.ai/solutions/community
[2] https://www.liquid.ai/pricing
[3] https://www.amd.com/en/blogs/2026/liquid-ai-amd-ryzen-on-device-meeting-summaries.html
[4] https://developer.puter.com/ai/liquid/lfm2-8b-a1b/
[5] https://docs.liquid.ai/deployment/on-device/ollama
[6] https://openrouter.ai/liquid/lfm-2.5-1.2b-instruct:free
[7] https://docs.liquid.ai/deployment/gpu-inference/vllm
[8] https://www.linkedin.com/posts/mlech26l_ai-machinelearning-ondeviceai-activity-7353073190673281024-moJf
[9] https://pypi.org/project/liquidai/
[10] https://github.com/Liquid4All/liquid-audio
[11] https://pypi.org/org/liquidai/
[12] https://github.com/orgs/Liquid4All/repositories
[13] https://github.com/Liquid4All/LiquidRULER
[14] https://github.com/Liquid4All/cookbook
[15] https://github.com/Liquid4All
[16] https://github.com/heyfoz/python-openai-chatcompletion

