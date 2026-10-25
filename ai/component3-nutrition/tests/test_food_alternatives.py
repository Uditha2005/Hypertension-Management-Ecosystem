"""Tests for cautious USDA alternative discovery."""
from food_alternatives import find_food_alternatives
from usda_fooddata import FoodSearchResult, USDAFoodRecord
from meal_plan_nutrients import NutrientProfile

class FakeClient:
    def __init__(self, records, searches): self.records, self.searches = records, searches
    def get_food(self, fdc_id): return self.records[int(fdc_id)]
    def search_foods(self, query, page_size=25): return self.searches

def rec(fid, desc, dtype, sodium, potassium, energy, satfat, ref="g", serving=None, serving_unit=None):
    return USDAFoodRecord(fid, desc, dtype, NutrientProfile(sodium_mg=sodium,potassium_mg=potassium,energy_kcal=energy,sat_fat_g=satfat),100 if ref=="g" else 1,ref,serving,serving_unit)

def test_alternatives_return_better_matching_records_without_substitution():
    original=rec(1,"Romaine lettuce", "Branded", 5, None, 18, 0, "serving", 85, "g")
    generic=rec(2,"Romaine lettuce, raw", "Survey (FNDDS)", 23, 260, 21, 0.039)
    fake=FakeClient({1:original,2:generic},[FoodSearchResult(2,"Romaine lettuce, raw","Survey (FNDDS)",None,None)])
    result=find_food_alternatives(fake,1,"g",5)
    assert result["missing_nutrients"] == ["potassium_mg"]
    assert result["alternatives"][0]["fdc_id"] == 2
    assert result["alternatives"][0]["fills_missing_nutrients"] == ["potassium_mg"]
    assert fake.records[1] is original

def test_alternatives_reject_incompatible_volume_serving_for_gram_quantity():
    original=rec(1,"Orange juice", "Branded", 0, 451, 110, None, "serving", 240, "ml")
    alt=rec(2,"Orange juice", "Branded", 0, 188, 46, 0, "serving", 240, "ml")
    fake=FakeClient({1:original,2:alt},[FoodSearchResult(2,"Orange juice","Branded",240,"ml")])
    result=find_food_alternatives(fake,1,"g",5)
    assert result["alternatives"] == []
