from __future__ import annotations

import importlib
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

if TYPE_CHECKING:
    from app.scrapers.base import BaseCountyScraper

_STUB = "app.scrapers.generic_stub.GenericStubScraper"

_ADAPTER_MAP: dict[str, str] = {
    # Texas — PropAccess iSite API
    "travis_tx":      "app.scrapers.tx_travis.TravisCountyScraper",
    "harris_tx":      "app.scrapers.tx_harris.HarrisCountyScraper",
    "dallas_tx":      "app.scrapers.tx_dallas.DallasCountyScraper",
    "tarrant_tx":     "app.scrapers.tx_tarrant.TarrantCountyScraper",
    "bexar_tx":       "app.scrapers.tx_bexar.BexarCountyScraper",
    "collin_tx":      "app.scrapers.tx_collin.CollinCountyScraper",
    "denton_tx":      "app.scrapers.tx_denton.DentonCountyScraper",
    "williamson_tx":  "app.scrapers.tx_williamson.WilliamsonCountyScraper",
    "montgomery_tx":  "app.scrapers.tx_montgomery.MontgomeryCountyScraper",
    "bastrop_tx":     "app.scrapers.tx_bastrop.BastropCountyScraper",
    "hays_tx":        "app.scrapers.tx_hays.HaysCountyScraper",
    # Florida — FL Property Appraiser PApublicServiceProxy API
    "miami_dade_fl":   "app.scrapers.fl_miami_dade.MiamiDadeScraper",
    "broward_fl":      "app.scrapers.fl_broward.BrowardCountyScraper",
    "palm_beach_fl":   "app.scrapers.fl_palm_beach.PalmBeachCountyScraper",
    "hillsborough_fl": "app.scrapers.fl_hillsborough.HillsboroughCountyScraper",
    "orange_fl":       "app.scrapers.fl_orange.OrangeCountyFLScraper",
    "pinellas_fl":     "app.scrapers.fl_pinellas.PinellasCountyScraper",
    "duval_fl":        "app.scrapers.fl_duval.DuvalCountyScraper",
    # California — ArcGIS open-data FeatureServer
    "san_diego_ca":    "app.scrapers.ca_san_diego.SanDiegoScraper",
    "los_angeles_ca":  "app.scrapers.ca_los_angeles.LosAngelesCountyScraper",
    "orange_ca":       "app.scrapers.ca_orange.OrangeCountyCAScraper",
    "riverside_ca":    "app.scrapers.ca_riverside.RiversideCountyScraper",
    "santa_clara_ca":  "app.scrapers.ca_santa_clara.SantaClaraCountyScraper",
    # Other states — ArcGIS open-data / Socrata
    "cook_il":         "app.scrapers.il_cook.CookCountyScraper",
    "king_wa":         "app.scrapers.wa_king.KingCountyScraper",
    "maricopa_az":     "app.scrapers.az_maricopa.MaricopaCountyScraper",
    "clark_nv":        "app.scrapers.nv_clark.ClarkCountyScraper",
    "fulton_ga":       "app.scrapers.ga_fulton.FultonCountyScraper",
    "mecklenburg_nc":  "app.scrapers.nc_mecklenburg.MecklenburgCountyScraper",
    "wake_nc":         "app.scrapers.nc_wake.WakeCountyScraper",
    # Verified working public APIs (Socrata)
    "ny_nyc":          "app.scrapers.ny_nyc.NYCCountyScraper",
    "ca_sf":           "app.scrapers.ca_sf.SanFranciscoCountyScraper",
    "pa_philly":       "app.scrapers.pa_philly.PhillyCountyScraper",
}


class ScraperRegistry:
    @classmethod
    def get(cls, adapter_name: str) -> type[BaseCountyScraper] | None:
        module_path = _ADAPTER_MAP.get(adapter_name)
        if not module_path:
            return None
        module_name, class_name = module_path.rsplit(".", 1)
        module = importlib.import_module(module_name)
        return getattr(module, class_name)

    @classmethod
    def get_for_county(cls, county_id: uuid.UUID, db: Session) -> type[BaseCountyScraper] | None:
        from app.models.county import County

        county = db.get(County, county_id)
        if not county:
            return None
        return cls.get(county.scraper_adapter)

    @classmethod
    def list_adapters(cls) -> list[str]:
        return list(_ADAPTER_MAP.keys())
