SALIENT_QUESTIONS_JSON_SHAPE = (
    '{"questions": ["<question 1>", "<question 2>", "<question 3>"]}'
)

INSIGHTS_JSON_SHAPE = (
    '{"insights": ['
    '{"insight": "<text>", "citation_statement_numbers": [1, 5, 3]}, '
    '{"insight": "<text>", "citation_statement_numbers": [2, 4]}'
    "]}"
)

IMPORTANCE_JSON_SHAPE = '{"importance": <int 1-10>}'

IMPORTANCE_BATCH_JSON_SHAPE = '{"importances": [<int 1-10>, <int 1-10>]}'

DAY_PLAN_JSON_SHAPE = (
    '{"items": ['
    '{"start_time": "<ISO-8601 datetime>", "end_time": "<ISO-8601 datetime later than start_time>", '
    '"location": "<location>", "action_content": "<action text>"}'
    "]}"
)

HOURLY_PLAN_JSON_SHAPE = (
    '{"items": ['
    '{"start_time": "<ISO-8601 datetime>", "end_time": "<ISO-8601 datetime later than start_time>", '
    '"location": "<location>", "action_content": "<action text>"}'
    "]}"
)

MINUTE_PLAN_JSON_SHAPE = (
    '{"items": ['
    '{"start_time": "<ISO-8601 datetime to minute precision>", "end_time": "<ISO-8601 datetime 5-15 minutes after start_time>", '
    '"location": "<location>", "action_content": "<action text>"}'
    "]}"
)
