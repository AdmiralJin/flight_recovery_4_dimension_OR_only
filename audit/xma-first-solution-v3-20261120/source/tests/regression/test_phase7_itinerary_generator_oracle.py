from backend.config import (
    ItineraryGenerationSource,
    PassengerItineraryGenerationConfig,
)
from backend.core import (
    brute_force_legal_passenger_itineraries,
    generate_passenger_itineraries,
    itinerary_semantic_key,
    validate_generated_passenger_itinerary,
)
from backend.schemas.columns import RecoveryColumns
from backend.schemas.scenario import Scenario


def test_smart_itinerary_generator_matches_exhaustive_oracle_and_breaks_bad_payload(
    toy_case_009_passenger_itinerary_generator_data,
    toy_case_009_passenger_itinerary_generator_columns_data,
):
    scenario = Scenario.model_validate(toy_case_009_passenger_itinerary_generator_data)
    columns = RecoveryColumns.model_validate(
        toy_case_009_passenger_itinerary_generator_columns_data
    )
    config = PassengerItineraryGenerationConfig(
        schema_version="1.0.0",
        profile_id="phase7_toy_oracle",
        default_mct_minutes=30,
        max_flight_legs=2,
        allow_unserved=True,
        allow_surface=False,
        source=ItineraryGenerationSource.TEST_FIXTURE,
        notes=("IMPLEMENTATION ASSUMPTION",),
    )
    passenger = scenario.passengers[0]
    smart = tuple(
        item
        for item in generate_passenger_itineraries(
            scenario, columns.flight_options, None, config
        )
        if item.pax_group_id == passenger.pax_group_id
    )
    brute = brute_force_legal_passenger_itineraries(
        scenario, columns.flight_options, passenger, config
    )
    assert {itinerary_semantic_key(item) for item in smart} == {
        itinerary_semantic_key(item) for item in brute
    }
    assert [
        (
            itinerary_semantic_key(item),
            item.arrival_time,
            item.arrival_delay_minutes,
        )
        for item in smart
    ] == [
        (
            itinerary_semantic_key(item),
            item.arrival_time,
            item.arrival_delay_minutes,
        )
        for item in brute
    ]

    transported = next(item for item in smart if item.arrival_time is not None)
    broken = transported.model_copy(update={"arrival_delay_minutes": 999})
    audit = validate_generated_passenger_itinerary(
        scenario, columns.flight_options, passenger, broken, config
    )
    assert not audit.valid
    assert "arrival_delay_mismatch" in audit.violations
