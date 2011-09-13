import time
from celery.execute import send_task

def get_services():
    import services
    all_services = []
    for service in services.__all__:
        if service != '__init__':
            all_services.append(service)
    return all_services

def stream(queries,services=None):
    """
    Yields latest public postings from major social networks for givenquery or
    queries.

    Keyword arguments:
    queries  -- a single query (string) or multiple queries (list)
    services -- a single service (string) or multiple services (list)

    """
    all_services = get_services()
    if services is None:
        services = all_services
    if type(queries) is str:
        queries = [queries]
    if type(services) is str:
        services = {services:{}}
    if type(services) is list:
        new_services = {}
        for service in services:
            if service in all_services:
                new_services[service] = {}
                new_services[service]['refresh_url'] = {}
        services = new_services
    print services
    for service in services:
        if service in all_services:
            services[service] = {}
            services[service]['refresh_url'] = {}
    tasks = []
    while True:
        for query in queries:
            time.sleep(1)
            for service in services:
                result = send_task('services.%s.feed' % service, [query, services[service]['refresh_url']]).get()
                if result:
                    services[service]['refresh_url'] = result[0]
                    taskset = result[1]
                    tasks.extend(taskset.subtasks)
                    while tasks:
                        current_task = tasks.pop(0)
                        if current_task.ready():
                            post = current_task.get()
                            if post is not None:
                                yield post
                        else:
                            tasks.append(current_task)

if __name__ == '__main__':
    for item in stream(['android','bitcoin'],['facebook','twitter']):
        print "%s | %s" % (item['service'],item['text'])
