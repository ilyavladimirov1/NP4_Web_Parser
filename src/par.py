import os

from bs4 import BeautifulSoup
import requests
from sqlalchemy.orm import Session
import matplotlib.pyplot as plt
import pandas as pd
import logging
from modules import engine, Film, Tag

LOG_FILE = os.getenv('LOG_FILE', 'my_log.log')
logging.basicConfig(filename=LOG_FILE, filemode='w', format='%(message)s',
                    level=logging.INFO)

# Подключаемся к сайту
site = os.getenv('site', 'https://www.kinoafisha.info/rating/movies/')
logging.info(f'Отправляем запрос на сайт {site}')
response = requests.get(site)
soup = BeautifulSoup(response.text, 'html.parser')
logging.info('Получили ответ от сайта.')

# Парсим ссылки на все страницы
pages = soup.find_all('a', {'class': 'bricks_item'})[4:14]

mv_links = []
for page_url in pages:
    page_response = requests.get(page_url['href'])
    soup = BeautifulSoup(page_response.text, 'html.parser')
    #  Извлекаем ссылки на фильмы по ссылке страницы
    movies_tags = soup.find_all('a', {'class': 'movieItem_title'})
    links_movies = [tag['href'] for tag in movies_tags]
    mv_links.extend(links_movies)

session = Session(bind=engine)

for i, url_m in enumerate(mv_links):
    mv_response = requests.get(url_m)
    soup = BeautifulSoup(mv_response.text, 'html.parser')

    #  Извлекаем данные фильма
    title = soup.find('h1', {'class': "trailer_title"}).get_text()[:-6]
    year = int(soup.find('span', {'class': "trailer_year"}).get_text()[:4])
    rating = float(soup.find('span', {'class': "rating_num"}).get_text())

    # Получаем или создаем фильм в базе данных
    film_i = session.query(Film).filter_by(title=title, year=year).first()
    if not film_i:
        film_i = Film(title=title, year=year, rating=rating)
        session.add(film_i)
        logging.info(f'Вставляем фильм "{title}" в базу данных. Год - {year}, рейтинг - {rating}, ссылка - {url_m}')

    # Добавление всех тегов на странице фильма
    cur_tags = soup.find_all('span', {'class': "filmInfo_genreItem button-main"})
    tags_name = list(map(lambda x: x.get_text(), cur_tags))

    # Добавляем теги к фильму
    for tag_name in tags_name:
        tag = session.query(Tag).filter_by(name=tag_name).first()
        if not tag:
            tag = Tag(name=tag_name)
            session.add(tag)
        if tag not in film_i.tags:
            film_i.tags.append(tag)
            logging.info(f'Добавляем тег "{tag.name}" к фильму "{film_i.title}".')

    session.commit()

# Запрос к базе данных для среднего рейтинга фильмов с тегом по годам
logging.info('Выполняем запрос...')
query = """
SELECT t.name AS tag_name, 
       f.year AS release_year, 
       AVG(f.rating) AS average_rating
FROM tags t
JOIN film_tags ft ON t.id = ft.tag_id
JOIN films f ON f.id = ft.film_id
GROUP BY t.name, f.year
"""
df = pd.read_sql_query(query, engine)
logging.info('Запрос выполнен.')

# Построение графиков изменения среднего рейтинга фильмов с определенным тегом по годам
for t_name in df['tag_name'].unique():
    t_data = df[df['tag_name'] == t_name]
    plt.plot(t_data['release_year'], t_data['average_rating'])
    plt.title(t_name)
    plt.xlabel('Год')
    plt.ylabel('Средний рейтинг')
    plt.show()

session.close()
logging.info('Соединение с базой данных закрыто.')
