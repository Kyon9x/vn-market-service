Feature: Error Handling and Edge Cases
  As a system user
  I want appropriate error responses
  So that I can handle failures gracefully

  Background:
    Given the market data service is running

  @error-handling
  Scenario: Invalid symbol handling
    Given I request data for an invalid symbol
    When I call the quote endpoint
    Then I should receive a 404 error
    And the error message should be descriptive

  @error-handling
  Scenario: Empty search query handling
    Given I provide an empty search query
    When I call the search endpoint
    Then I should receive a validation error
    And the error should indicate missing query parameter

  @error-handling
  Scenario: Invalid date range for history
    Given I request historical data with invalid dates
    When I call the history endpoint
    Then I should receive a validation error
    And the error should describe the date format issue

  @error-handling
  Scenario: Service unavailable simulation
    Given the external data source is unavailable
    When I request market data
    Then I should receive appropriate error handling
    And the response should indicate retry possibility