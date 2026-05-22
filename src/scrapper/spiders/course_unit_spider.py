import getpass
import scrapy

import sqlite3

from scrapy.http import Request, FormRequest
from urllib.parse import urlparse, parse_qs, urlencode
from configparser import ConfigParser, ExtendedInterpolation
from datetime import datetime
import logging
import json

from scrapper.settings import CONFIG, PASSWORD, USERNAME

from ..database.Database import Database
from ..items import CourseUnit

class CourseUnitSpider(scrapy.Spider):
    name = "course_units"
    allowed_domains = ['sigarra.up.pt']
    course_units_ids = set()

    def open_config(self):
        """
        Reads and saves the configuration file. 
        """
        config_file = "./config.ini"
        self.config = ConfigParser(interpolation=ExtendedInterpolation())
        self.config.read(config_file) 

    def __init__(self, *args, **kwargs):
        super(CourseUnitSpider, self).__init__(*args, **kwargs)
        self.open_config()
        logging.getLogger('scrapy').propagate = False

    # def format_login_url(self):
    #     return '{}?{}'.format(self.login_page_base, urlencode({
    #         'pv_login': self.user,
    #         'pv_password': self.password
    #     }))

    def start_requests(self):
        "This function is called before crawling starts."
        return self.courseRequests()
    
    # def login_response_err(self, failure):
    #     print('Login failed. SIGARRA\'s response: error type 404;\nerror message "{}"'.format(failure))
    #     print("Check your password")
    
    # def check_login_response(self, response):
    #     """Check the response returned by a login request to see if we are
    #     successfully logged in. Since we used the mobile login API endpoint,
    #     we can just check the status code.
    #     """ 

    #     if response.status == 200:
    #         response_body = json.loads(response.body)
    #         if response_body['authenticated']:
    #             self.log("Successfully logged in. Let's start crawling!")
    #             return self.courseRequests()
           

    def courseRequests(self):
        print("Gathering course units") 
        db = Database() 

        ALLOWED_COURSE_IDS = {10861}  # MESW só estes cursos
        #LEIC, MEIC, MIA, MESW, MM 22841, 30901, 22862, 10861, 732
        sql = """
            SELECT course.id, year, course.id, faculty.acronym 
            FROM course JOIN faculty 
            ON course.faculty_id= faculty.acronym
        """
        db.cursor.execute(sql)
        self.courses = db.cursor.fetchall()
        db.connection.close()

        self.log("Crawling {} courses".format(len(self.courses)))

        for course in self.courses:
            if int(course[0]) not in ALLOWED_COURSE_IDS:
                print(f"[courseRequests] Skipping course ID: {course[0]}")
                continue

            url = 'https://sigarra.up.pt/{}/pt/ucurr_geral.pesquisa_ocorr_ucs_list?pv_ano_lectivo={}&pv_curso_id={}'.format(
                course[3], course[1], course[2])
            print(f"[courseRequests] Course ID: {course[0]} | Faculty: {course[3]} | Year: {course[1]} | URL: {url}")
            yield scrapy.http.Request(
                url=url,
                meta={'course_id': course[0]},
                callback=self.extractSearchPages)
    def extractSearchPages(self, response):
        print(f"[extractSearchPages] URL: {response.url} | Status: {response.status}")
        last_page_url = response.css(
            ".paginar-saltar-barra-posicao > div:last-child > a::attr(href)").extract_first()
        last_page = int(parse_qs(urlparse(last_page_url).query)[
            'pv_num_pag'][0]) if last_page_url is not None else 1
        print(f"[extractSearchPages] Total pages: {last_page}")
        for x in range(1, last_page + 1):
            page_url = response.url + "&pv_num_pag={}".format(x)
            print(f"[extractSearchPages] Fetching page {x}: {page_url}")
            yield scrapy.http.Request(
                url=page_url,
                meta=response.meta,
                callback=self.extractCourseUnits)

    def extractCourseUnits(self, response):
        print(f"[extractCourseUnits] URL: {response.url} | Status: {response.status}")
        course_units_table = response.css("table.dados .d")
        print(f"[extractCourseUnits] Found {len(course_units_table)} course units")

        for course_unit_row in course_units_table:
            unit_url = response.urljoin(course_unit_row.css(".t > a::attr(href)").extract_first())
            print(f"[extractCourseUnits] Course unit URL: {unit_url}")
            yield scrapy.http.Request(
                url=unit_url,
                meta=response.meta,
                callback=self.extractCourseUnitInfo)

    def extractCourseUnitInfo(self, response):
        print(f"[extractCourseUnitInfo] URL: {response.url} | Status: {response.status}")
        name = response.xpath(
            '//div[@id="conteudoinner"]/h1[2]/text()').extract_first().strip()

        if name == 'Sem Resultados':
            print(f"[extractCourseUnitInfo] Sem Resultados for URL: {response.url}")
            return None

        course_unit_id = parse_qs(urlparse(response.url).query)['pv_ocorrencia_id'][0]

        acronym = response.xpath(
            '//div[@id="conteudoinner"]/table[@class="formulario"][1]//td[text()="Sigla:"]/following-sibling::td[1]/text()').extract_first()

        if acronym is None: 
            acronym = response.xpath(
                '//div[@id="conteudoinner"]/table[@class="formulario"][1]//td[text()="Acronym:"]/following-sibling::td[1]/text()').extract_first()

        if acronym is not None:
            acronym = acronym.replace(".", "_")

        url = response.url
        schedule_url = response.xpath('//a[text()="Horário"]/@href').extract_first()
        print(f"[extractCourseUnitInfo] Name: {name} | Acronym: {acronym} | Schedule URL: {schedule_url}")

        occurrence = response.css('#conteudoinner > h2::text').extract_first()
        semester = occurrence[24:26].strip()
        year = int(occurrence[12:16])

        print(f"[extractCourseUnitInfo] Semester: {semester} | Year: {year}")

        assert semester == '1S' or semester == '2S' or semester == 'A' or semester == 'SP' \
            or semester == '1T' or semester == '2T' or semester == '3T' or semester == '4T'
        assert year > 2000

        semesters = []
        if semester == '1S' or semester == '1T' or semester == '2T':
            semesters = [1]
        elif semester == '2S' or semester == '3T' or semester == '4T':
            semesters = [2]
        elif semester == 'A':
            semesters = [1, 2]

        for semester in semesters:
            if (course_unit_id not in self.course_units_ids):
                self.course_units_ids.add(course_unit_id)
                print(f"[extractCourseUnitInfo] Yielding CourseUnit: {name} (ID: {course_unit_id})")
                yield CourseUnit(
                    id=course_unit_id,
                    course_id=response.meta['course_id'],
                    name=name,
                    acronym=acronym,
                    url=url,
                    schedule_url=schedule_url,
                    year=year,
                    semester=semester,
                    last_updated=datetime.now(),
                )
            else:
                print(f"[extractCourseUnitInfo] Skipping CourseUnit: {name} (ID: {course_unit_id}) - already seen or no schedule")
                yield None

    
