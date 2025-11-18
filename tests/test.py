from vnstock import Company

company = Company(symbol='ACB', source='VCI')
company.overview().to_csv('acb_overview.csv')