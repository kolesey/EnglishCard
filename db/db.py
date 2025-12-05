from dotenv import load_dotenv
import os
import psycopg2

load_dotenv()
HOST = os.environ.get('HOST')
PORT = os.environ.get('PORT')
DATABASE = os.environ.get('DATABASE')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')

# Проверяем все ли настройки БД есть в переменных окружения
if any(item is None for item in [HOST, PORT, DATABASE, DB_USER, DB_PASS]):
    raise ValueError('Параметры подключения к БД не установлены в переменных окружения.')

def create_db_connection():
    conn = psycopg2.connect(host=HOST, port=PORT, database=DATABASE, user=DB_USER, password=DB_PASS)
    return conn

def create_tables(conn):
    with conn.cursor() as cur:
        cur.execute("""
                CREATE TABLE IF NOT EXISTS users(
                    user_id BIGINT PRIMARY KEY,
                    name VARCHAR(100) NOT NULL
                    );
                """)

        cur.execute("""
                CREATE TABLE IF NOT EXISTS words(
                    word_id SERIAL PRIMARY KEY,
                    rus_word VARCHAR(100),
                    en_word VARCHAR(100),
                    wrong_answer INTEGER NOT NULL DEFAULT 0,
                    right_answer INTEGER NOT NULL DEFAULT 0,
                    user_id BIGINT NOT NULL REFERENCES users(user_id)
                    );
                """)

        conn.commit()

def add_user(conn, user_id, user_name):
    """
    Функция добавляет пользователя в БД
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param user_name: имя пользователя для добавления
    :return: количество строк в результате выполнения функции
    """
    with conn.cursor() as cur:
        cur.execute("""
                INSERT INTO users (user_id, name)
                VALUES (%s, %s);
                """, (user_id, user_name))
        conn.commit()
        return cur.rowcount

def add_words(conn, user_id, ru_word, en_word):
    """
    Функция сохраняет пару RU-EN слов в БД
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param ru_word: русское слово
    :param en_word: перевод русского слова
    :return: количество строк в результате выполнения функции
    """
    with conn.cursor() as cur:
        cur.execute("""
                INSERT INTO words (rus_word, en_word, user_id)
                VALUES (%s, %s, %s)
                """, (ru_word, en_word, user_id))
        conn.commit()
        return cur.rowcount

def find_user(conn, user_id):
    """
    Функция ищет в БД пользователя по его id в telegram
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :return: Имя пользователя если он есть в БД или None если его нет
    """
    with conn.cursor() as cur:
        cur.execute("""
                SELECT name
                  FROM users
                 WHERE user_id = %s
                """, (user_id,))
        return cur.fetchone()

def count_words(conn, user_id):
    """
    Функция считает сколько слов в словаре у конкретного пользователя
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :return: int количество слов в словаре у пользователя
    """
    with conn.cursor() as cur:
        cur.execute("""
                SELECT COUNT(*)
                  FROM words
                 WHERE user_id = %s
                """, (user_id,))
        return cur.fetchone()[0]

def take_random_word(conn, user_id):
    """
    Функция выбирает из БД случайную пару EN-RU слов из 5 слов с худшими результатами по ответам
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :return: кортеж с парой En-Ru слов
    """
    with conn.cursor() as cur:
        # Выбираем из 5 слов с худшими результатами, одно случайное
        cur.execute("""
                SELECT rus_word, en_word
                  FROM (
                SELECT rus_word, en_word
                  FROM words 
                 WHERE user_id = %s
                 ORDER BY ((wrong_answer + 1.0) / (right_answer + 1.0)) DESC                 
                 LIMIT 5
                 )
                 ORDER BY RANDOM() LIMIT 1
                """, (user_id,))
        return cur.fetchone()

def take_other_words(conn, user_id, ex_word, lang, count=5):
    """
    Функция выбирает случайные слова, за исключением одного из БД
    для предложения их в качестве неправильных вариантов ответов
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param ex_word: слово, которое не должно попасть в выборку (правильный вариант ответа)
    :param lang: язык на котором должны быть слова
    :param count: количество возвращаемых слов
    :return: list из случайных слов
    """
    with conn.cursor() as cur:
        if lang == 'ru':
            cur.execute("""
                    SELECT rus_word
                      FROM words
                     WHERE user_id = %s AND rus_word <> %s
                     ORDER BY RANDOM() LIMIT %s;                     
                    """, (user_id, ex_word, count))
        else:
            cur.execute("""
                    SELECT en_word
                      FROM words
                     WHERE user_id = %s AND en_word <> %s
                     ORDER BY RANDOM() LIMIT %s;                     
                    """, (user_id, ex_word, count))

        result = cur.fetchall()
        return [x[0] for x in result]

def del_word(conn, user_id, word):
    """
    Функция удаляет слово из БД
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param word: слово, которое надо удалить
    :return: количество строк в результате выполнения функции
    """

    with conn.cursor() as cur:
        cur.execute("""
                DELETE FROM words
                 WHERE user_id = %s AND (rus_word = %s OR en_word = %s);
                """, (user_id, word, word))
        conn.commit()
        return cur.rowcount

def add_rigt_answer(conn, user_id, word):
    """
    Функция увеличивает на 1 счетчик правильных ответов для слова
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param word: слово для которого надо увеличить счетчик
    :return: None
    """
    with conn.cursor() as cur:
        cur.execute("""
                UPDATE words
                   SET right_answer = right_answer + 1
                 WHERE user_id = %s AND (rus_word = %s OR en_word = %s);
                """, (user_id, word, word))
        conn.commit()


def add_wrong_answer(conn, user_id, word):
    """
    Функция увеличивает на 1 счетчик неправильных ответов для слова
    :param conn: объект connection
    :param user_id: номер пользователя в telegram
    :param word: слово для которого надо увеличить счетчик
    :return: None
    """
    with conn.cursor() as cur:
        cur.execute("""
                UPDATE words
                   SET wrong_answer = wrong_answer + 1
                 WHERE user_id = %s AND (rus_word = %s OR en_word = %s);
                """, (user_id, word, word))
        conn.commit()

if __name__ == '__main__':
    conn = create_db_connection()

    conn.close()