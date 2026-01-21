import enum


class ZoneType(str, enum.Enum):
    ACTIVE_EFFECT_CARD_SLOT_1_P1 = "active_effect_card_slot_1_p1"
    ACTIVE_EFFECT_CARD_SLOT_2_P1 = "active_effect_card_slot_2_p1"
    ACTIVE_EFFECT_CARD_SLOT_3_P1 = "active_effect_card_slot_3_p1"
    ACTIVE_EFFECT_CARD_SLOT_1_P2 = "active_effect_card_slot_1_p2"
    ACTIVE_EFFECT_CARD_SLOT_2_P2 = "active_effect_card_slot_2_p2"
    ACTIVE_EFFECT_CARD_SLOT_3_P2 = "active_effect_card_slot_3_p2"
    ACTIVE_EFFECT_CARD_SLOT_1_P3 = "active_effect_card_slot_1_p3"
    ACTIVE_EFFECT_CARD_SLOT_2_P3 = "active_effect_card_slot_2_p3"
    ACTIVE_EFFECT_CARD_SLOT_3_P3 = "active_effect_card_slot_3_p3"
    ACTIVE_EFFECT_CARD_SLOT_1_P4 = "active_effect_card_slot_1_p4"
    ACTIVE_EFFECT_CARD_SLOT_2_P4 = "active_effect_card_slot_2_p4"
    ACTIVE_EFFECT_CARD_SLOT_3_P4 = "active_effect_card_slot_3_p4"
    ACTIVE_EFFECT_CARD_SLOT_1_P5 = "active_effect_card_slot_1_p5"
    ACTIVE_EFFECT_CARD_SLOT_2_P5 = "active_effect_card_slot_2_p5"
    ACTIVE_EFFECT_CARD_SLOT_3_P5 = "active_effect_card_slot_3_p5"

    SABOTAGED_CARD_AREA_P1 = "sabotaged_card_area_p1"
    SABOTAGED_CARD_AREA_P2 = "sabotaged_card_area_p2"
    SABOTAGED_CARD_AREA_P3 = "sabotaged_card_area_p3"

    HAND_P1 = "hand_p1"
    HAND_P2 = "hand_p2"
    HAND_P3 = "hand_p3"
    HAND_P4 = "hand_p4"
    HAND_P5 = "hand_p5"

    RESEARCH_DECK = "research_deck"
    RESEARCH_DISCARD = "research_discard"
    INFLUENCE_DECK = "influence_deck"
    INFLUENCE_DISCARD = "influence_discard"
    SABOTAGE_DECK = "sabotage_deck"
    SABOTAGE_DISCARD = "sabotage_discard"

    BOARD = "board"


class ComponentType(str, enum.Enum):
    CARD = "card"


class CardCategory(str, enum.Enum):
    RESEARCH = "research"
    INFLUENCE = "influence"
    SABOTAGE = "sabotage"
