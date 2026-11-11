"""Safe scoped diagnostics for the future regional client (not an incident feed)."""
from datetime import timedelta
from core import utc, covers

LABELS = {'water': 'воде', 'power': 'электричеству', 'mchs': 'МЧС'}


def snapshot(store, municipality, now, *, pending_counts=None):
    utc(now)
    sources = []
    for channel in store.channels.values():
        row = store.db.execute('SELECT success,attempt,error,gap FROM health WHERE channel=?',
                               (channel['id'],)).fetchone()
        sources.append({
            'id': channel['id'], 'url': channel['url'],
            'enabled': bool(channel.get('enabled')),
            'lastSuccessAt': row[0] if row else None,
            'lastAttemptAt': row[1] if row else None,
            'errorCode': row[2] if row else None,
            'historyGap': bool(row and row[3]),
        })
    categories = {}
    for category, label in LABELS.items():
        status = store.category_status(category, municipality, now)
        relevant = [c for c in store.channels.values() if c.get('enabled')
                    and c.get('identity_verified') and category in c.get('categories', [])
                    and covers(c,category,municipality)]
        rows = [s for s in sources if s['id'] in {c['id'] for c in relevant}]
        reviews = (pending_counts.get(category, 0) if pending_counts is not None else
                   sum(p.get('requiresReview', False) for c in relevant for p in store.posts(c['id'])))
        if status['state'] == 'unconfigured':
            message = f'Охват по {label} для выбранной территории пока не подтверждён'
        elif status['state'] == 'unavailable':
            has_cache = any(store.posts(c['id']) for c in relevant)
            message = f'Информация по {label} временно недоступна. ' + ('Сохранённые публикации доступны' if has_cache else 'Сохранённых публикаций пока нет')
        elif status['state'] == 'partial':
            message = f'Информация по {label} может быть неполной: часть каналов недоступна'
        else:
            message = 'Зарегистрированные каналы прочитаны. Полнота публикаций не гарантируется'
        if reviews:
            message += f'. Публикаций требуют проверки: {reviews}'
            if status['state'] == 'read':
                status['state'] = 'partial'
        categories[category] = dict(
            state=status['state'], message=message, sourceIds=[c['id'] for c in relevant],
            pendingReview=reviews, hasHistoryGap=any(s['historyGap'] for s in rows),
            # This is the oldest last success, not the most recent attempt.
            lastSuccessAt=min((s['lastSuccessAt'] for s in rows), key=utc)
                if rows and all(s['lastSuccessAt'] for s in rows) else None,
            coverage='partial' if relevant else 'unknown',
        )
    return {
        'schemaVersion': 1, 'mode': 'max-only', 'region': 'RU-ROS',
        'municipality': municipality, 'checkedAt': now,
        'kind': 'source-health-only', 'categoryHealth': categories, 'sources': sources,
        'notice': 'Отсутствие публикаций не подтверждает отсутствие аварий',
    }
