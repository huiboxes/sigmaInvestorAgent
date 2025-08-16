import json
import logging




def main(event, context):
    logger = logging.getLogger('func')
    logger.info('===start===')

    response = json.dumps({
        "result": "hello world"
    })

    return response
    


if __name__ == '__main__':
    print(main(None, None))