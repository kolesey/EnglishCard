from dotenv import load_dotenv
import os
import requests

load_dotenv()
YANDEX_TOKEN = os.environ.get('YANDEX_TOKEN')
FOLDER_ID = os.environ.get('FOLDER_ID')

# from config import YANDEX_TOKEN, FOLDER_ID

def detect(word):
    """
    Функция определяет на каком языке введено слово
    :param word: слово, язык которого надо определить
    :return: str код языка для яндекс словаря ('en' или 'ru')
    """
    body = {
        "text": word,
        "folderId": FOLDER_ID,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Api-Key {0}".format(YANDEX_TOKEN),
    }

    response = requests.post(
        "https://translate.api.cloud.yandex.net/translate/v2/detect",
        json=body,
        headers=headers,
    )
    resp = response.json()
    if 'languageCode' in resp:
        return resp['languageCode']
    else:
        return False

def translate(word):
    """
    Функция осуществляет перевод слова или фразы посредством API Яндекс переводчика
    :param word: слово или фраза, которые нужно перевести
    :return: словарь с переводом и определенным языком. Например:
    translate('silo')
    {'translations': [{'text': 'бункер', 'detectedLanguageCode': 'en'}]}
    """

    word_lang = detect(word)
    if not word_lang:
        return False

    if word_lang == 'ru':
        target_language = 'en'
    elif word_lang == 'en':
        target_language = 'ru'
    else:
        return False
    body = {
        "targetLanguageCode": target_language,
        "texts": word,
        "folderId": FOLDER_ID,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": "Api-Key {0}".format(YANDEX_TOKEN),
    }

    response = requests.post(
        "https://translate.api.cloud.yandex.net/translate/v2/translate",
        json=body,
        headers=headers,
    )
    return response.json()

if __name__ == "__main__":
    # print(detect('lf;k;dlfkg;ldfk d;f;lgk d;lkg;dfg d;fg kd;fgkl d;fgd f;lgk d;flgd fgdf;lgk d;flgk d;fg '))
    # print(translate('lf;k;dlfkg;ldfk d;f;lgk d;lkg;dfg d;fg kd;fgkl d;fgd f;lgk d;flgd fgdf;lgk d;flgk d;fg '))
    print(translate('silo'))