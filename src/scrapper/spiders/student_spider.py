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

class StudentSpider(scrapy.Spider):
    name = "student"
    allowed_domains = ['sigarra.up.pt']
    login_page_base = 'https://sigarra.up.pt/feup/pt/mob_val_geral.autentica'

    def open_config(self):
        config_file = "./config.ini"
        self.config = ConfigParser(interpolation=ExtendedInterpolation())
        self.config.read(config_file) 

    def __init__(self, *args, **kwargs):
        super(StudentSpider, self).__init__(*args, **kwargs)
        self.open_config()
        self.user = CONFIG[USERNAME]
        self.password = CONFIG[PASSWORD]
        logging.getLogger('scrapy').propagate = False

    def format_login_url(self):
         return '{}?{}'.format(self.login_page_base, urlencode({
             'pv_login': self.user,
             'pv_password': self.password
         }))
    #https://sigarra.up.pt/feup/pt/mob_val_geral.autentica?pv_login=&pv_password=

    def start_requests(self):
        "Login first, then start crawling."
        print("[StudentSpider] Logging in...")
        yield Request(
            url=self.format_login_url(),
            callback=self.check_login_response,
            errback=self.login_response_err
        )
    
    def login_response_err(self, failure):
        print('Login failed. SIGARRA\'s response: error type 404;\nerror message "{}"'.format(failure))
        print("Check your password")
    
    def check_login_response(self, response):
        """Check the response returned by a login request to see if we are
     successfully logged in. Since we used the mobile login API endpoint,
     we can just check the status code.
     """ 

        if response.status == 200:
            response_body = json.loads(response.body)
            if response_body['authenticated']:
                self.log("Successfully logged in. Let's start crawling!")
                return self.student_Requests()
           

    def student_Requests(self):
        print("Gathering students enroled in the units") 
        db = Database() 

        sql = """
            SELECT id 
            FROM course_unit
        """
        db.cursor.execute(sql)
        course_units =[row[0] for row in db.cursor.fetchall()] #lista com todas as unidades curriculares
        db.connection.close()

        print(f"[StudentSpider] Found {len(course_units)} course units")


        for course_unit_id in course_units:
            
            url = f'https://sigarra.up.pt/feup/pt/mob_ucurr_geral.uc_inscritos?pv_ocorrencia_id={course_unit_id}'
            print(f"[StudentSpider] Fetching students from Courseunit ID: {course_unit_id} | URL: {url}")
            yield scrapy.http.Request(
                url=url,
                meta={'course_unit_id': course_unit_id},
                callback=self.parse_students
                )

    def parse_students(self, response):
        course_unit_id=response.meta['course_unit_id']

        try:
            data = json.loads(response.body)
        except json.JSONDecodeError:
            print(f"[StudentSpider] Failed to parse JSON for course unit {course_unit_id}")
            return

        print(f"[StudentSpider] Course unit {course_unit_id} → {len(data)} students")

        db = Database()
        for student in data:
            student_id = student.get("codigo")
            if student_id:
                try:
                    db.cursor.execute(
                        "INSERT OR IGNORE INTO students_in_course_units (student_id, course_unit_id) VALUES (?, ?)",
                        (student_id, course_unit_id)
                    )
                except Exception as e:
                    print(f"[StudentSpider] Error inserting student {student_id}: {e}")

        db.connection.commit()
        db.connection.close()
   
    