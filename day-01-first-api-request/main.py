from openai import OpenAI


client = OpenAI()

print("Отправляем запрос в OpenAI...")
response = client.responses.create(
    model="gpt-5.6",
    input="Назови три практических применения больших языковых моделей.",
)

print("Ответ модели:")
print(response.output_text)

