# refactor gold client to improve some points:

## use cache to feed /search/history/VN.GOLD start_date to end_date
  the main issue: 
    - someevery time user call this endpoint to query historical data for GOLD. we call in loop to vnstock to get data.
  solution:
    - logic updated to query cache first
    - detect missing data date from cache between start_date to end_date
    - create function to call to vnstock to only query data for missing dates
    - update and push data to cache if found
## support gold unit price
  idea: for now the gold price in database is in L (Lượng) unit for vietnamese market. I want to support L and C. where L = 10C (Chỉ)
  Solution to do it:
    - refactor symbol to only supprort: VN.GOLD (the original one default is L) and VN.GOLD.C
    - the price store in db and cache is not change. still default is L.
    - in user layer we just devide price from database from L to C if user query C.

