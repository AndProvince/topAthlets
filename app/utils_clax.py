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
            # Преобразуем формат 02h06'01.180 → 02:06:01.180
            val = val.replace('h', ':').replace("'", ':').replace(',', '.')
            return pd.to_timedelta(val)
        except:
            return None

    df_result['finish_td'] = df_result['t'].apply(parse_time)
    has_milliseconds = df_result['finish_td'].apply(
        lambda td: getattr(td, 'microseconds', 0) != 0 if pd.notnull(td) else False
        ).any()

    def timedelta_to_str(td, show_milliseconds=True):
        if pd.isnull(td):
            return "DNF"
        total_seconds = td.total_seconds()
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        seconds = int(total_seconds % 60)
        hundredths = round((total_seconds - int(total_seconds)) * 100)

        if show_milliseconds:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{hundredths:02d}"
        else:
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    df_result['finish_time'] = df_result['finish_td'].apply(lambda td: timedelta_to_str(td, has_milliseconds))

    # Создаём дисциплины
    for distance in df_distances["nom"]:
        df_filtered_result = df_result[df_result["p"] == distance]

        if 'to' in df_filtered_result.columns:
            df_filtered_result['to'] = pd.to_numeric(df_filtered_result['to'], errors='coerce').fillna(-1).astype(int)

            df_sorted_result = df_filtered_result.sort_values(
                by=['to', 'finish_td'],
                ascending=[False, True]
            )
        else:
            df_sorted_result = df_filtered_result.sort_values(by='finish_td', ascending=True)

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
                time=row["finish_time"],
                point=0
            )
            db.session.add(participant)

        db.session.commit()

    return True

