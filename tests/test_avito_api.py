"""Tests for parser/avito_api.py — JSON extraction and parsing."""
import json
import pytest

from parser.avito_api import AvitoAPI, _extract_price, _deep_find_description


class TestExtractPrice:
    def test_int(self):
        assert _extract_price(15000) == 15000

    def test_float(self):
        assert _extract_price(15000.0) == 15000

    def test_dict_value(self):
        assert _extract_price({"value": 25000}) == 25000

    def test_dict_price(self):
        assert _extract_price({"price": 25000}) == 25000

    def test_string(self):
        assert _extract_price("25 000₽") == 25000

    def test_string_nbsp(self):
        assert _extract_price("25\xa0000") == 25000

    def test_string_invalid(self):
        assert _extract_price("бесплатно") == 0

    def test_none(self):
        assert _extract_price(None) == 0

    def test_list(self):
        assert _extract_price([1, 2, 3]) == 0


class TestExtractJsonFromHtml:
    def test_mime_invalid_script(self):
        html = '''
        <html><body>
        <script type="mime/invalid">{"state":{"catalog":{"items":[{"id":1}]}}}</script>
        </body></html>
        '''
        data = AvitoAPI._extract_json_from_html(html)
        assert "catalog" in data
        assert data["catalog"]["items"][0]["id"] == 1

    def test_mime_invalid_with_data_key(self):
        html = '''
        <html><body>
        <script type="mime/invalid">{"data":{"catalog":{"items":[{"id":2}]}}}</script>
        </body></html>
        '''
        data = AvitoAPI._extract_json_from_html(html)
        assert "catalog" in data

    def test_no_scripts(self):
        html = "<html><body><p>No scripts here</p></body></html>"
        data = AvitoAPI._extract_json_from_html(html)
        assert data == {}

    def test_html_entities(self):
        html = '''
        <html><body>
        <script type="mime/invalid">{"state":{"item":{"title":"iPhone 15 &amp; case"}}}</script>
        </body></html>
        '''
        data = AvitoAPI._extract_json_from_html(html)
        assert data["item"]["title"] == "iPhone 15 & case"


class TestFindCatalogItems:
    def test_path_catalog_items(self):
        data = {"catalog": {"items": [{"id": 1}, {"id": 2}]}}
        items = AvitoAPI._find_catalog_items(data)
        assert len(items) == 2

    def test_path_data_catalog(self):
        data = {"data": {"catalog": {"items": [{"id": 3}]}}}
        items = AvitoAPI._find_catalog_items(data)
        assert len(items) == 1

    def test_path_items_direct(self):
        data = {"items": [{"id": 4}]}
        items = AvitoAPI._find_catalog_items(data)
        assert len(items) == 1

    def test_empty(self):
        assert AvitoAPI._find_catalog_items({}) == []


class TestExtractImages:
    def test_gallery_large_urls(self):
        item = {"gallery": {"image_large_urls": ["http://img1.jpg", "http://img2.jpg"]}}
        urls = AvitoAPI._extract_images(item)
        assert len(urls) == 2

    def test_gallery_single(self):
        item = {"gallery": {"imageLargeUrl": "http://img1.jpg"}}
        urls = AvitoAPI._extract_images(item)
        assert urls == ["http://img1.jpg"]

    def test_images_dict_sizes(self):
        item = {"images": [{"640x480": "http://img1.jpg"}, {"640x480": "http://img2.jpg"}]}
        urls = AvitoAPI._extract_images(item)
        assert len(urls) == 2

    def test_empty(self):
        assert AvitoAPI._extract_images({}) == []


class TestExtractParamsStr:
    def test_iva_steps(self):
        item = {
            "iva": {
                "DescriptionStep": [{
                    "componentData": {
                        "payload": {"text": "256 ГБ, серый"}
                    }
                }],
                "FirstLineStep": [{
                    "componentData": {
                        "payload": {"text": "iPhone 15 Pro"}
                    }
                }],
            }
        }
        result = AvitoAPI._extract_params_str(item)
        assert "256 ГБ" in result
        assert "iPhone 15 Pro" in result

    def test_no_iva(self):
        assert AvitoAPI._extract_params_str({}) == "N/A"


class TestDeepFindDescription:
    def test_shallow(self):
        data = {"description": "A nice phone for sale"}
        assert _deep_find_description(data) == "A nice phone for sale"

    def test_nested(self):
        data = {"item": {"description": "A nice phone for sale"}}
        assert _deep_find_description(data, max_depth=2) == "A nice phone for sale"

    def test_too_short(self):
        data = {"description": "short"}
        assert _deep_find_description(data) == ""

    def test_no_description(self):
        data = {"title": "something", "price": 100}
        assert _deep_find_description(data) == ""

    def test_max_depth(self):
        data = {"a": {"b": {"c": {"d": {"description": "deep description text here"}}}}}
        assert _deep_find_description(data, max_depth=2) == ""
        assert _deep_find_description(data, max_depth=4) == "deep description text here"


class TestGetEmbeddedRedirect:
    def test_state_redirect(self):
        data = {"redirect": "/moskva/telefony"}
        assert AvitoAPI._get_embedded_redirect(data) == "/moskva/telefony"

    def test_data_url_redirect(self):
        data = {"data": {"status": {"code": 301}, "url": "/moskva/smartfony"}}
        assert AvitoAPI._get_embedded_redirect(data) == "/moskva/smartfony"

    def test_no_redirect(self):
        data = {"catalog": {"items": []}}
        assert AvitoAPI._get_embedded_redirect(data) is None


class TestBuildSearchUrl:
    def test_basic(self):
        url = AvitoAPI._build_search_url("iPhone 15")
        assert "q=iPhone+15" in url or "q=iPhone%2015" in url
        assert "s=104" in url

    def test_with_price(self):
        url = AvitoAPI._build_search_url("MacBook", price_max=100000)
        assert "pmax=100000" in url

    def test_with_page(self):
        url = AvitoAPI._build_search_url("iPad", page=3)
        assert "p=3" in url

    def test_page_1_no_param(self):
        url = AvitoAPI._build_search_url("iPad", page=1)
        assert "p=" not in url


class TestSetPage:
    def test_set_page(self):
        url = "https://www.avito.ru/all?q=test&s=104"
        result = AvitoAPI._set_page(url, 2)
        assert "p=2" in result

    def test_replace_page(self):
        url = "https://www.avito.ru/all?q=test&p=1&s=104"
        result = AvitoAPI._set_page(url, 3)
        assert "p=3" in result
        assert "p=1" not in result

    def test_remove_page(self):
        url = "https://www.avito.ru/all?q=test&p=5&s=104"
        result = AvitoAPI._set_page(url, 1)
        assert "p=" not in result


class TestEnsureSortByDate:
    def test_adds_sort_param(self):
        url = "https://www.avito.ru/all/telefony?q=iphone"
        result = AvitoAPI._ensure_sort_by_date(url)
        assert "s=104" in result
        assert "q=iphone" in result

    def test_preserves_existing_sort(self):
        url = "https://www.avito.ru/all/telefony?q=iphone&s=1"
        result = AvitoAPI._ensure_sort_by_date(url)
        assert "s=1" in result
        assert "s=104" not in result

    def test_no_query_params(self):
        url = "https://www.avito.ru/all/telefony/mobilnye_telefony/apple-ASgBAgICAkS0wA3OqzmwwQ"
        result = AvitoAPI._ensure_sort_by_date(url)
        assert "s=104" in result


class TestExtractSellerData:
    def test_total_items_count(self):
        data = {"seller": {"itemsCount": 25}}
        result = AvitoAPI._extract_seller_data_from_ad_data(data)
        assert result["active_items"] == 25

    def test_category_items_count(self):
        data = {"seller": {"itemsCount": 25, "categoryItemsCount": 5}}
        result = AvitoAPI._extract_seller_data_from_ad_data(data)
        assert result["active_items"] == 25
        assert result["category_items"] == 5

    def test_seller_type_shop(self):
        data = {"seller": {"type": "магазин"}}
        result = AvitoAPI._extract_seller_data_from_ad_data(data)
        assert result["seller_type"] == "shop"

    def test_seller_type_developer_id(self):
        data = {"seller": {"developerId": 12345}}
        result = AvitoAPI._extract_seller_data_from_ad_data(data)
        assert result["seller_type"] == "shop"

    def test_empty_data(self):
        result = AvitoAPI._extract_seller_data_from_ad_data({})
        assert result["active_items"] == 0
        assert result["category_items"] == 0
        assert result["seller_type"] == ""

    def test_text_items_count(self):
        data = {"seller": {"itemsText": "47 объявлений"}}
        result = AvitoAPI._extract_seller_data_from_ad_data(data)
        assert result["active_items"] == 47

    def test_nested_data_seller(self):
        data = {"data": {"seller": {"activeItems": 12}}}
        result = AvitoAPI._extract_seller_data_from_ad_data(data)
        assert result["active_items"] == 12


class TestExtractDescriptionFromAdData:
    def test_item_path(self):
        data = {"item": {"description": "Great phone, barely used, comes with box"}}
        assert "Great phone" in AvitoAPI._extract_description_from_ad_data(data)

    def test_data_item_path(self):
        data = {"data": {"item": {"description": "Selling my laptop, excellent condition"}}}
        assert "Selling my laptop" in AvitoAPI._extract_description_from_ad_data(data)

    def test_buyer_item_path(self):
        data = {"buyerItem": {"description": "Original Apple Watch Series 9 for sale"}}
        assert "Apple Watch" in AvitoAPI._extract_description_from_ad_data(data)

    def test_empty(self):
        assert AvitoAPI._extract_description_from_ad_data({}) == ""

    def test_short_description_ignored(self):
        data = {"item": {"description": "ok"}}
        assert AvitoAPI._extract_description_from_ad_data(data) == ""
