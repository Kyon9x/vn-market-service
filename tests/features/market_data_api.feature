Feature: Market Data API Endpoints
  As a Wealthfolio user
  I want to retrieve market data for Vietnamese assets
  So that I can view portfolio values and make investment decisions

  Background:
    Given the market data service is running
    And the service health check passes

  @smoke @stocks
  Scenario: Stock data retrieval workflow
    Given I search for stocks with a common symbol
    When I select the first search result
    And I request the latest quote for that symbol
    Then I should receive valid quote data
    And the quote should contain price information
    When I request historical data for the past 365 days
    Then I should receive historical price records
    And the history should contain multiple trading days
    And all data should be in VND currency

  @smoke @funds
  Scenario: Fund data retrieval workflow
    Given I search for mutual funds with a fund symbol
    When I select the first search result
    And I request the latest NAV for that fund
    Then I should receive valid NAV data
    And the NAV should contain net asset value
    When I request historical NAV data for the past year
    Then I should receive historical NAV records
    And the history should show daily NAV values

  @smoke @indices
  Scenario: Index data retrieval workflow
    Given I search for market indices
    When I select VNINDEX from the results
    And I request the latest index value
    Then I should receive valid index data
    And the index should contain current points
    When I request historical index data
    Then I should receive index history
    And the data should show market trends

  @smoke @gold
  Scenario: Gold price retrieval workflow
    Given I search for gold prices
    When I select SJC gold from the results
    And I request the latest gold price
    Then I should receive valid gold price data
    And the price should be in VND per tael
    When I request historical gold prices
    Then I should receive gold price history
    And the history should show price fluctuations

  @regression
  Scenario Outline: Asset type data retrieval
    Given I search for <asset_type> with query <query>
    When I select the first search result to get the symbol
    And the symbol should not be empty
    Then I request the latest data for that symbol
    Then I should receive valid latest data
    And the data should contain relevant information
    When I request the historical data for the past 365 days for that symbol
    Then I should receive valid historical data
    And the data should not be empty

    Examples:
      | asset_type | symbol |
      | stocks     | VNM    |
      | funds      | DCDS   |
      | indices    | VNINDEX|
      | gold       | SJC    |