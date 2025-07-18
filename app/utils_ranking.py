from . import db
from .models import Race, Discipline, Participant
from sqlalchemy import func, extract
from datetime import datetime, timedelta

def get_ranking(search_query=None):
    # if one_year_ago is None:
        # Берем данные за последний год
        # one_year_ago = datetime.today().replace(month=1, day=1)  # Можно использовать с начала года
        # one_year_ago = datetime.today() - timedelta(days=365)

    period_end = datetime.today()
    period_start = datetime.today() - timedelta(days=365)

    query = (
        db.session.query(
            Participant.email,
            func.sum(Participant.point).label('total_points'),
            func.count(Participant.id).label('num_races'),
            func.coalesce(func.max(Participant.name), Participant.email).label('display_name')
        )
        .join(Discipline)
        .join(Race)
        .filter(Race.date >= period_start)
        .filter(Race.date <= period_end)
    )

    if search_query is not None:
        query = query.filter(Participant.name.ilike(f"%{search_query}%"))

    ranking = (
        query.group_by(Participant.email)
        .order_by(func.sum(Participant.point).desc())
        .all()
    )

    return ranking, period_start, period_end
