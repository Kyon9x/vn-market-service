2025-11-02 16:44:31,965 - app.cache.historical_cache - INFO - Missing 3 dates in 1 ranges

2025-11-02 16:44:31,965 - app.clients.fund_client - INFO - Fetching 1 missing date ranges for DCIP

2025-11-02 16:44:31,965 - app.cache.rate_limit_protector - INFO - Rate limit reached, waiting 0.1s...

2025-11-02 16:44:32,047 - app.cache.rate_limit_protector - INFO - Rate limit cleared after 1 waits

2025-11-02 16:44:32,047 - app.clients.fund_client - INFO - Fetching NAV history for DCIP (attempt 1/2)...

2025-11-02 16:44:32,146 - app.utils.provider_logger - INFO - [provider=call] [provider_name=vnstock] method=fund_client._fetch_fund_nav_report_from_provider status=success duration=96ms fund_id=id_            date  nav_per_unit

0     2019-04-03      10000.00

1     2019-04-09       9995.43

2     2019-04-16       9991.69

3     2019-04-23       9987.93

4     2019-04-30       9994.93

...          ...           ...

1235  2025-10-27      11737.06

1236  2025-10-28      11736.96

1237  2025-10-29      11738.81

1238  2025-10-30      11740.36

1239  2025-10-31      11745.04


[1240 rows x 2 columns]
