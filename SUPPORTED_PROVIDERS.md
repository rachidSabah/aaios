# Supported LLM Providers in AAiOS
## Version 5.3.2 — Enterprise Provider Routing

AAiOS routes all language model queries through a central **Model Router** featuring cost metrics, rate limiting, and automated failovers.

### 1. Built-in LLM Providers

| Provider | API Endpoint / SDK | Supported Features | Default Model |
| :--- | :--- | :--- | :--- |
| **Anthropic** | Native SDK / Claude API | Vision, Tool Calling, System Prompts | `claude-3-5-sonnet` |
| **OpenAI** | Native SDK / ChatCompletions | Vision, Tool Calling, Structured Outputs | `gpt-4o` |
| **Google** | Gemini API | Multi-modal, Long Context | `gemini-1.5-pro` |
| **DeepSeek** | DeepSeek API / OpenAI compatible | Low-cost reasoning, Coder | `deepseek-coder` |
| **Ollama** | Local Host (`localhost:11434`) | Local execution, Offline run | `llama3.1` |
| **LM Studio** | Local Host / OpenAI compatible | Local sandbox models | Custom |
| **NVIDIA** | NIM Endpoints | High-throughput inferencing | Custom |
| **Groq** | Groq Cloud SDK | Ultra-low latency chat | `llama3-70b` |
| **Azure** | Azure OpenAI Service | Enterprise security, Private endpoints | Custom |
| **Mistral** | Mistral API | Multi-lingual, Tool calling | `mistral-large` |

---

### 2. Custom Provider Registry
To add a custom provider, implement the `ModelProvider` interface in `services/model_router/providers/base.py` and register it in `providers/`:
```python
from services.model_router.providers.base import ModelProvider

class CustomProvider(ModelProvider):
    # Implement abstract methods
    pass
```
