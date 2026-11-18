import dotenv
from gigachat import GigaChat
from gigachat.models import ChatMessage, ChatCompletionRequest
import os
import json

class chat_bot:
    SYSTEM_PROMPT = """
    Ты — опытный IT-рекрутер и эксперт по безопасности. Твоя задача — проанализировать вакансию и принять решение об отклике.
    МОЙ ПРОФИЛЬ:
    - Студент 4 курса, очного формата обучения в университете МТИ, по прикладной математике и информатике, ищу позицию Стажер/Trainee/Junior/Middle.
    - Навыки: средний уровень разработки на Python, средний уровень знаний C#, Git, понимание ООП, YAML, json, .env, написание ботов, работа с API, requests, Godot, создание игр, сборка ПК, ремонт ПК и ноутбуков на базовом уровне, диагностика, поиск багов, тестирование, базы данных, анализ данных, работа с ИИ, работа с LLM, API, REST API, Linux, Windows, Excel, Word, презентации, высокий уровень английский язык, программирование, .NET, Backend
    ВАКАНСИЯ ДЛЯ АНАЛИЗА:
    - Должность: {vacancy_title}
    - Компания: {company_name}
    - Зарплата: {salary}
    - Описание: {vacancy_description}
    - Требуемые навыки: {vacancy_skills}
    ЗАДАЧА:
    1. Оцени вакансию на признаки скама или несоответствия моему профилю.
    2. Если вакансия адекватна, составь короткое (3-4 абзаца), убедительное сопроводительное письмо на русском языке, подчеркивающее мои релевантные навыки для ЭТОЙ конкретной вакансии.
    ФОРМАТ ОТВЕТА:
    Верни ответ СТРОГО в формате JSON без какого-либо дополнительного текста, маркдауна или пояснений. Используй следующую схему:
    {
      "is_scam": true/false,
      "scam_reason": "причина, если скам, иначе пустая строка",
      "match_score": число от 0 до 100,
      "cover_letter": "текст сопроводительного письма, если is_scam == false и имеет match_score выше 50, иначе пустая строка"
    }
    """


    def __init__(self):
        # self.model = "meta-llama/llama-3-8b-instruct:free"
        dotenv.load_dotenv()
        API_KEY = os.getenv("api_key")
        self.client = GigaChat(
            model="GigaChat-3-Pro",
            credentials=API_KEY,
            verify_ssl_certs=False
     )
        print(self.client.get_models())

    def ask_bot(self, text):
        request = ChatCompletionRequest(
            messages=[
                ChatMessage(role="system", content=self.SYSTEM_PROMPT),
                ChatMessage(role="user", content=text)
            ],
            temperature=0.1  # Низкая температура для строгого следования JSON-схеме
        )
        response = self.client.chat.create(request)
        raw_answer = response.messages[0].content[0].text
        # logger.info("✅ Ответ получен!")

        # Спасательный круг: убираем ```json, если модель всё-таки его добавила
        clean_answer = raw_answer.strip().removeprefix("```json").removesuffix("```").strip()

        # Проверяем, что это валидный JSON, прежде чем вернуть
        try:
            return json.loads(clean_answer)
        except json.JSONDecodeError:
            print("⚠️ GigaChat вернул не JSON! Сырой ответ:\n", raw_answer)
            return None
        except Exception as e:
            print(f"❌ Ошибка при запросе к GigaChat: {e}")
            return None
