from openai import OpenAI


client = OpenAI()

print("Введите сообщение. Для выхода используйте exit или quit.")

while True:
    prompt = input("\nВы: ").strip()

    if prompt.lower() in {"exit", "quit"}:
        break

    if not prompt:
        continue

    print("Отправляем запрос в OpenAI...")
    response = client.responses.create(
        model="gpt-5.6",
        input=prompt,
    )

    print("Ответ модели:")
    print(response.output_text)
