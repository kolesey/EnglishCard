import requests

def get_random_word():
    """
    Функция обращается к стороннему сервису для получения случайного слова на англ. языке
    :return: str случайное слово на англ. языке
    """
    response = requests.get('https://random-word-api.herokuapp.com/word')
    return response.json()[0]


if __name__ == '__main__':
    print(get_random_word())