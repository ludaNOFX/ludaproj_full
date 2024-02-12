from flask import current_app


def add_to_index(index, model):
    if not current_app.elasticsearch:
        return
    if current_app.elasticsearch is not None:
        try:
            payload = {}
            for field in model.__searchable__:
                payload[field] = getattr(model, field)
            current_app.elasticsearch.index(index=index, id=model.id, body=payload)
        except Exception as e:
            current_app.logger.error(f"Elasticsearch indexing error: {e}")


def remove_from_index(index, model):
    if not current_app.elasticsearch:
        return
    if current_app.elasticsearch is not None:
        try:
            current_app.elasticsearch.delete(index=index, id=model.id)
        except Exception as e:
            current_app.logger.error(f"Elasticsearch indexing error: {e}")


def query_index(index, query, page, per_page):
    if not current_app.elasticsearch:
        return [], 0
    search = current_app.elasticsearch.search(
        index=index,
        body={'query': {'multi_match': {'query': query, 'fields': ['*']}},
              'from': (page - 1) * per_page, 'size': per_page})
    ids = [int(hit['_id']) for hit in search['hits']['hits']]
    return ids, search['hits']['total']['value']

