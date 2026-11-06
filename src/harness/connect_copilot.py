from litellm import completion
from litellm.types.utils import ModelResponse

response = completion(
    model="github_copilot/claude-sonnet-5.5",
    messages=[{"role": "user", "content": "Hello"}],
)

assert isinstance(response, ModelResponse)

print(response.choices[0].message.content)
