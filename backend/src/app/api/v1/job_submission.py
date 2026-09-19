from app.api.v1.dependencies import get_job_execution_store


def submit_job(service, key, payload, create):
    store = get_job_execution_store()
    job_id = store.enqueue(key, payload, create)
    return service.get_job(job_id)
