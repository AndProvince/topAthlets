import xml.etree.ElementTree as ET
import os
import pandas as pd
from flask import current_app
from .models import db, Discipline, Participant
from datetime import datetime

def get_date_str():
    return datetime.now().strftime("%Y%m%d%H%M%S_")

def get_node_attrib_data(node):
    results = []
    for item in node:
        results.append(item.attrib)

    return pd.DataFrame(results)

# def get_data_df(file):
#     tree = ET.parse(file)
#     root = tree.getroot()
#
#     df_main = pd.DataFrame([root.attrib])
#
#     df_engages = get_node_attrib_data(root.find('Etapes').find('Etape').find('Engages'))
#     df_engages.rename({'m': 'm_engage'}, axis=1, inplace=True)
#
#
#     df_results = get_node_attrib_data(root.find('Etapes').find('Etape').find('Resultats'))
#     df_points = get_node_attrib_data(root.find('Etapes').find('Etape').find('Pointages'))
#     df_categories = get_node_attrib_data(root.find('Categories').find('G'))
#     df_teams = get_node_attrib_data(root.find('Equipes'))
#     df_sert = get_node_attrib_data(root.find('lflfel'))
#     df_distances = get_node_attrib_data(root.find('Parcours'))
#     df_filters = get_node_attrib_data(root.find('Editions'))
#     df_countries = get_node_attrib_data(root.find('Pays'))
#
#     df_result = df_engages.merge(df_results, how='left', on='d')
#
#     df_result = df_result.fillna('-')
#
#     def parse_time(val):
#         try:
#             return pd.to_datetime(val, format="%Hh%M'%S").time()
#         except:
#             return None
#
#     df_result['finish_time'] = df_result['t'].apply(parse_time)
#     # df_result['finish_time'] = df_result['finish_time'].fillna("DNF")
#     df_result['finish_td'] = pd.to_timedelta(df_result['finish_time'].astype(str), errors='coerce')
#
#     # # Столбец с возрасными группами без указания пола (последние два символа)
#     # df_result['groups'] = df_result['ca'].str[:-2].fillna('-')
#
#     return df_result, df_distances
#
#
# result, distances = get_data_df('amangeldy2023.clax')
# result.to_csv('race_results.csv', index=False)
# print("Готово! Сохранено в race_results.csv")
# print(result.head())
# print(distances)

def parse_clax_and_create_disciplines(file_path, race):
    """
    Парсит .clax файл и создаёт дисциплины для данного соревнования.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    race_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'results', str(race.id))
    os.makedirs(race_path, exist_ok=True)

    tree = ET.parse(file_path)
    root = tree.getroot()

    # Парсим дистанции
    df_distances = get_node_attrib_data(root.find('Parcours'))
    df_distances.to_csv(os.path.join(race_path, get_date_str() + "disciplines.csv"), index=False)

    # Парсим участников (engages) и результаты
    df_engages = get_node_attrib_data(root.find('Etapes').find('Etape').find('Engages'))
    df_engages.rename({'m': 'm_engage'}, axis=1, inplace=True)

    df_results = get_node_attrib_data(root.find('Etapes').find('Etape').find('Resultats'))
    df_result = df_engages.merge(df_results, how='left', on='d').fillna('-')

    # Обработка времени
    def parse_time(val):
        try:
            return pd.to_datetime(val, format="%Hh%M'%S").time()
        except Exception:
            return None

    df_result['finish_time'] = df_result['t'].apply(parse_time)
    df_result['finish_time'] = df_result['finish_time'].fillna("DNF")
    df_result['finish_td'] = pd.to_timedelta(df_result['finish_time'].astype(str), errors='coerce')

    # Создаём дисциплины
    for distance in df_distances["nom"]:
        df_filtered_result = df_result[df_result["p"] == distance]
        df_sorted_result = df_filtered_result.sort_values(by='finish_td')
        df_sorted_result.reset_index(inplace=True, drop=True)

        result_file_orig = f"{distance}_result.csv"
        result_file = get_date_str() + result_file_orig
        df_sorted_result.to_csv(os.path.join(race_path, result_file), index=False)

        discipline = Discipline(
            race_id=race.id,
            name=distance,
            result_file_orig=result_file_orig,
            result_file="results/" + str(race.id) + "/" + result_file,
            participants_count=df_sorted_result.shape[0]
        )

        db.session.add(discipline)
        db.session.commit()

        # Добавляем участников
        for index, row in df_sorted_result.iterrows():
            participant = Participant(
                discipline_id=discipline.id,
                index=index+1,
                name=row["n"],
                numder=row["d"],
                email=row["e"],
                phone=row["tl"],
                pace=row["m"],
                time=row["finish_time"].strftime("%H:%M:%S") if row["finish_time"] != "DNF" else "DNF",
                point=0
            )
            db.session.add(participant)

        db.session.commit()

    return True

