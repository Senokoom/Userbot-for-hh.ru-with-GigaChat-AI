import time
import os
import undetected_chromedriver as uc
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from random import *
from rapidfuzz import fuzz, process
from undetected_chromedriver import WebElement
import yaml
from chat_bot import chat_bot
import logging
from hashlib import md5
import json

def setup_logger():
    # Создаем логгер
    logger = logging.getLogger("WorkFinderBot")
    logger.setLevel(logging.DEBUG) # Ловим всё, от отладки до критических ошибок

    # Формат сообщений: [ВРЕМЯ] УРОВЕНЬ: Сообщение
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Обработчик для консоли (выводит INFO и выше)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # 2. Обработчик для файла (сохраняет всё, включая DEBUG)
    # Файл будет создаваться в папке с проектом
    file_handler = logging.FileHandler("bot_activity.log", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Добавляем обработчики к логгеру (проверяем, чтобы не дублировать при повторном импорте)
    if not logger.handlers:
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)

    return logger

# Инициализируем логгер глобально
logger = setup_logger()


class browser_bot:
    def __init__(self):

        self.vacancies_path = os.path.abspath("logged_vacancies.yaml")
        logger.info("Загружаю yaml с посещенными вакансиями")

        if not os.path.exists(self.vacancies_path):
            open(self.vacancies_path, mode='w', encoding='utf-8').close()

        with open(self.vacancies_path, mode='r', encoding='utf-8') as file:
            if yaml.safe_load(file) is None:
                self.visited_vacancies = set()
            else: self.visited_vacancies:set = set(yaml.safe_load(file))

        self.chat_bot = chat_bot()
        self.BANNED_WORDS = ["бариста", "продаж", "клиента", "менеджер", "электросамокат", "курьер"]
        profile_path = os.path.abspath("chrome-profile")
        logger.info(f"Использую профиль: {profile_path}")
        os.makedirs(profile_path, exist_ok=True)

        # Запускаем браузер
        self.driver = uc.Chrome(user_data_dir=profile_path)

        logger.info("Перехожу на hh.ru...")
        self.driver.get("https://hh.ru")

        self.main_window = self.driver.window_handles[0]


    def check_vacancy_in_visited(self, vacancy):
        if not self.visited_vacancies:
            return False
        vacancy_hash = md5(json.dumps(vacancy, sort_keys=True).encode('utf-8')).hexdigest()
        if vacancy_hash in self.visited_vacancies:
            return True
        return False


    def add_vacancy_to_visited(self, vacancy):
        logger.info(f"Добавляю вакансию {vacancy} к посещенным")
        vacancy_hash = md5(json.dumps(vacancy, sort_keys=True).encode('utf-8')).hexdigest()
        self.visited_vacancies.add(vacancy_hash)
        return


    def save_visited_vacancies_to_file(self):
        logger.info("Сохраняем посещенные вакансии в память")
        with open(self.vacancies_path, mode='w', encoding='utf-8') as file:
            yaml.dump(sorted(self.visited_vacancies), file)



    def check_title_for_banned_words(self, vacancy_name):
        match = process.extractOne(vacancy_name.lower(), self.BANNED_WORDS, scorer=fuzz.partial_ratio)
        logger.info(f"На работе с названием: '{vacancy_name}' Matched '{match[0]}' with {match[1]:.1f}% similarity")
        if match and match[1] >= 85:
            return True
        vacancy_split = vacancy_name.split(' ')
        for word in vacancy_split:
            if word.lower() in self.BANNED_WORDS:
                return True
        return False

    def main_loop(self):
        counter = 0
        self.check_authorization()
        if self.is_authorized:
            time.sleep(randint(5, 8) * 0.3)
            self.move_to_search_tab()
            try:
                while self.get_next_page_element():
                    time.sleep(randint(5, 15) * 0.3)
                    vacancies = self.get_vacancy()
                    logger.info(f"Получил {len(vacancies)} вакансий на этой странице")
                    vacancy_number = 0
                    for vacancy in vacancies:
                        vacancy_number += 1
                        logger.info(f"Рассматриваю вакансию номер {vacancy_number}")
                        if counter >= 5:
                            counter = 0
                            self.save_visited_vacancies_to_file()
                        time.sleep(randint(5, 8) * 0.3)
                        self.move_to_element(vacancy)
                        vacancy_base_info = self.get_vacancy_dict(vacancy)
                        logger.info(f"Выбрали вакансию {vacancy_base_info}")
                        if self.check_vacancy_in_visited(vacancy_base_info):
                            logger.info(f"Пропустили вакаснию {vacancy_base_info} из-за того, что уже видели ее")
                            continue
                        if self.check_title_for_banned_words(vacancy_base_info["name"]):
                            self.add_vacancy_to_visited(vacancy_base_info)
                            logger.info(f"Пропустили вакаснию {vacancy_base_info} из-за забаненных слов")
                            counter += 1
                            continue
                        vacancy.click()
                        self.switch_to_new_window()
                        vacancy_info = self.parse_vacancy(vacancy_base_info) #если тут больше чем 2 None. нахуй его
                        if vacancy_info.count("НетИнформации") >= 2:
                            logger.info(f"Пропустили вакансию: {vacancy_base_info}, из-за недостаточности данных о ней на площадке")
                            self.add_vacancy_to_visited(vacancy_base_info)
                            time.sleep(randint(5, 8) * 0.3)
                            self.close_the_window()
                            self.switch_to_main_window()
                            counter += 1
                            continue
                        response = self.check_vacancy(vacancy_info)
                        time.sleep(randint(5, 8) * 0.3)
                        logger.info(f"Получили ответ от ИИ: {response}")
                        if response is not None:
                            if not response[list(response.keys())[0]]:
                                try:
                                    if int(response[list(response.keys())[2]]) >= 60:
                                        self.answer_to_vacancy(response[list(response.keys())[-1]])
                                        logger.info("Отправили резюме")
                                except:
                                    self.answer_to_vacancy(response[list(response.keys())[-1]])
                                    logger.info("Отправили резюме")
                        self.add_vacancy_to_visited(vacancy_base_info)
                        time.sleep(randint(5, 8) * 0.3)
                        self.close_the_window()
                        self.switch_to_main_window()
                        counter += 1
                    self.move_to_next_page()
            except Exception as e:
                logger.error(f"ПРОИЗОШЛА ОШИБКА {e}. Ожидаю инпута от пользователя")
                input()





    def check_authorization(self):
        logger.info("Проверяю авторизацию...")
        try:
            # Ждем до 10 секунд, пока на странице не появится элемент с текстом "Мои резюме"
            # Это маркер того, что пользователь вошел в систему
            wait = WebDriverWait(self.driver, randint(7, 12))
            element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Отклики')]"))
            )
            logger.info("✅ Отлично! Авторизация подтверждена. Бот готов к работе.")
            self.is_authorized = True
        except Exception:
            logger.error("❌ ВНИМАНИЕ: Авторизация не обнаружена!")
            print("👉 Пожалуйста, войдите в аккаунт в открывшемся браузере вручную.")
            print("👉 После успешного входа нажмите Enter здесь, чтобы продолжить...")
            input()
            self.is_authorized = False

    def move_to_search_tab(self):
        logger.info("Перемещается в поиск")
        wait = WebDriverWait(self.driver, randint(5, 7))
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Поиск')]")))
            element.click()
        except:
            logger.error("❌ ВНИМАНИЕ: Кнопка поиск не обнаружена!")

    def get_vacancy(self) -> list[WebElement]:
        logger.info("Получаем список вакансий")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, "//article[@data-qa='vacancy-serp__vacancy']")))
            found_elements = self.driver.find_elements(By.XPATH, "//article[@data-qa='vacancy-serp__vacancy']")
            return found_elements
        except:
            logger.error("❌ ВНИМАНИЕ: Вакансии не обнаружены")
            a: list[WebElement] = []
            return a

    def get_next_page_element(self):
        logger.info("Получаем элемент следующей страницы")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, "//nav[@data-qa='pager-block']")))
            element = element.find_element(By.XPATH, "//a[@data-qa='pager-next']")
            return element
        except Exception as e:
            logger.error(e)
            return False

    def move_to_next_page(self):
        logger.info("Перемещаемся на следующую страницу")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, "//nav[@data-qa='pager-block']")))
            element = element.find_element(By.XPATH, "//a[@data-qa='pager-next']")
            self.move_to_element(element)
            try:
                element.click()
            except:
                self.driver.execute_script("arguments[0].click();", element)
        except Exception as e:
            logger.error(e)
            return

    def move_to_element(self, element: WebElement):
        logger.info("Двигаемся к элементу")
        autochain = ActionChains(self.driver)
        try:
            while not element.is_displayed():
                autochain.scroll_by_amount(0, randint(150, 40))
                time.sleep(randint(5, 15) * 0.1)
        except:
            logger.error("❌ ВНИМАНИЕ: Проблема с скроллингом")
            return

    def go_to_my_resumes(self):
        logger.info("Идем в мои резюме")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, "//a[@data-qa='profileAndResumes-button']")))
            element.click()
        except:
            logger.error("No profile and resumes button")

    def get_my_resumes_elements(self):
        logger.info("Получаем элементы моих резюме")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@data-qa='compact-resume-list']")))
            elements = element.find_elements(By.XPATH, "//div[@data-qa='resume')]")
            return elements
        except:
            logger.error("❌ ВНИМАНИЕ: Резюме отстутствуют")

    def answer_to_vacancy(self, letter_text):
        logger.info("Отвечаем на вакансию(функция из фукнций)")
        time.sleep(randint(5, 10) * 0.1)
        self.send_resume()
        time.sleep(randint(5, 10) * 0.1)
        self.add_letter()
        time.sleep(randint(5, 10) * 0.1)
        self.add_letter_text(letter_text)
        time.sleep(randint(5, 10) * 0.1)
        self.send_resume_with_letter()
        time.sleep(randint(5, 10) * 0.1)
        return


    def send_resume(self):
        logger.info("Ищем кнопку Откликнуться(первую)")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, "//a[@data-qa='vacancy-response-link-top']")))
            self.move_to_element(element)
            element.click()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении кнопки Откликнуться: {e}")
            return "Кнопка не найдена"

    def add_letter(self):
        logger.info("Нажимаем на кнопку добавить сопроводительное письмо")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[@data-qa='add-cover-letter']")))
            element.click()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении кнопки Добавить сопроводительное: {e}")
            return "Описание не найдено"


    def send_resume_with_letter(self):
        logger.info("Отправляем резюме с заполненным сопроводительным письмом")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(
                EC.presence_of_element_located((By.XPATH, "//button[@data-qa='vacancy-response-submit-popup']")))
            element.click()
        except Exception as e:
            logger.error(f"❌ Ошибка при получении кнопки Откликнуться: {e}")
            return "Кнопка не найдена"


    def add_letter_text(self, letter_text):
        logger.info("Пишем сопроводительное письмо")
        try:
            # 1. Находим поле ввода по надежному data-qa
            textarea = self.driver.find_element(By.XPATH,
                                                "//textarea[@data-qa='vacancy-response-popup-form-letter-input']")

            # 2. Делаем поле активным (кливаем по нему), чтобы сфокусироваться
            textarea.click()

            # 3. Очищаем поле на всякий случай
            textarea.clear()
            rand = Random()
            for char in letter_text:
                textarea.send_keys(char)
                # Рандомная задержка между нажатиями клавиш (от 0.01 до 0.05 секунды)
                time.sleep(rand.uniform(0.01, 0.05))
        except Exception as e:
            logger.error(f"❌ Не удалось вставить текст в поле: {e}")



    def get_vacancy_description(self):
        logger.info("Получаем описание вакансии")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            element = wait.until(EC.presence_of_element_located((By.XPATH, "//div[@data-qa='vacancy-description']")))
            return element
        except Exception as e:
            logger.error(f"❌ Ошибка при получении описания вакансии: {e}")
            return None

    def get_vacancy_required_skills(self):
        logger.info("Получаем скиллы для вакансии")
        wait = WebDriverWait(self.driver, randint(7, 12))
        try:
            elements = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//li[@data-qa='skills-element']")))
            return elements
        except Exception as e:
            logger.error(f"❌ Ошибка при получении навыков вакансии: {e}")
            return None


    def parse_vacancy(self, vacancy_dict):
        logger.info("Парсим вакансию в понятный для ИИ вид")
        vac_desc = self.get_vacancy_description()
        vac_skills = self.get_vacancy_required_skills()
        result = f"{vacancy_dict}"
        result += f"Описание Вакансии: \n{vac_desc.text if vac_desc else "НетИнформации"}\nКлючевые навыки:\n{', '.join(list(map(lambda x: x.text, vac_skills))) if vac_skills else "НетИнформации"}"
        return result


    def switch_to_main_window(self):
        logger.info("Перемещаем курсор на главное окно")
        self.driver.switch_to.window(self.main_window)


    def close_the_window(self):
        logger.info("закрываем окно")
        self.driver.close()


    def switch_to_new_window(self):
        logger.info("Перемеещаем курсор на новое окно")
        windows = self.driver.window_handles
        for win in windows:
            if __name__ == '__main__':
                if win != self.main_window:
                    self.driver.switch_to.window(win)
                    return
        return

    def get_vacancy_dict(self, vacancy: WebElement):
        vacancy_dict = {
            "name": "",
            "salary": "",
            "company_name": ""
        }
        salary_words = ["на руки", "за месяц", "за год", "за смену", "до вычета налогов"]
        name = vacancy.text
        namelist = name.split('\n')
        # logger.info(f"Создаем словарь вакансии из {namelist}")
        shift = 1
        if "Сейчас смотр" in namelist[0]:
            vacancy_dict["name"] = namelist[1]
            shift = 0
        else:
            vacancy_dict["name"] = namelist[0]
        try:
            if any(item in namelist[2 - shift] for item in salary_words):
                vacancy_dict["salary"] = namelist[2 - shift].replace("\u202f", "")
        except:
            vacancy_dict["salary"] = "Не указано"
        vacancy_dict["company_name"] = namelist[4 - shift]
        return vacancy_dict

    def check_vacancy(self, vacancy_info):
        logger.info("Проверяю вакансию через ИИ")
        ai_answer = self.chat_bot.ask_bot(vacancy_info)
        return ai_answer

b = browser_bot()
b.main_loop()