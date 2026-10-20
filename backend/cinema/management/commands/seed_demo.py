import random
import unicodedata
from datetime import datetime, time, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone
from faker import Faker

from cinema.models import (
    Booking,
    BookedSeat,
    Cinema,
    CinemaHall,
    Genre,
    Movie,
    MovieGenre,
    Payment,
    Review,
    Screening,
    Seat,
    User,
)

SEED = 2403
USER_COUNT = 80
DAYS_BEFORE_TODAY = 7
DAYS_AFTER_TODAY = 6

# Kino nimi, linn, postiindeksi algus ja saalid: (nimi, ekraani tüüp, ridu, kohti reas).
CINEMAS = [
    ('Kino Tähesaal', 'Tallinn', '10', [('Saal 1', 'IMAX', 12, 18), ('Saal 2', '3D', 10, 14), ('Saal 3', '2D', 8, 12)]),
    ('Kino Emajõgi', 'Tartu', '51', [('Saal 1', '3D', 10, 14), ('Saal 2', '2D', 8, 12), ('Saal 3', '2D', 6, 10)]),
    ('Kino Rannahoov', 'Pärnu', '80', [('Saal 1', '2D', 9, 12), ('Saal 2', '3D', 7, 10), ('Saal 3', '2D', 5, 8)]),
]

GENRES = (
    'Draama', 'Komöödia', 'Põnevik', 'Ulme', 'Seiklus',
    'Animatsioon', 'Krimi', 'Romantika', 'Õudus', 'Dokumentaal',
)

# Väljamõeldud filmid: pealkiri, pikkus (min), vanusepiirang, keel, žanrid.
MOVIES = [
    ('Viimane rong Tapale', 112, 'K-12', 'eesti', ('Draama', 'Põnevik')),
    ('Saaremaa saladus', 98, 'MS-12', 'eesti', ('Krimi', 'Põnevik')),
    ('Kuu tagumine külg', 141, 'MS-12', 'inglise', ('Ulme', 'Seiklus')),
    ('Siil ja suur torm', 84, 'PERE', 'eesti', ('Animatsioon', 'Seiklus')),
    ('Talv Toomemäel', 105, 'MS-6', 'eesti', ('Romantika', 'Draama')),
    ('Pimeduse koridor', 96, 'K-16', 'inglise', ('Õudus', 'Põnevik')),
    ('Kalurite küla', 88, 'PERE', 'eesti', ('Dokumentaal',)),
    ('Neljas planeet', 128, 'MS-12', 'inglise', ('Ulme', 'Draama')),
    ('Pulm Peipsi ääres', 101, 'MS-6', 'eesti', ('Komöödia', 'Romantika')),
    ('Kadunud kompass', 117, 'MS-12', 'inglise', ('Seiklus', 'Komöödia')),
    ('Raudne talv', 133, 'K-14', 'soome', ('Draama',)),
    ('Robot nimega Rasmus', 90, 'PERE', 'eesti', ('Animatsioon', 'Komöödia', 'Ulme')),
    ('Öine valvur', 109, 'K-14', 'inglise', ('Krimi', 'Põnevik')),
    ('Hõbedane järv', 94, 'MS-6', 'soome', ('Romantika', 'Draama')),
    ('Metsa hääled', 79, 'PERE', 'eesti', ('Dokumentaal',)),
    ('Vaikne tänav', 99, 'K-16', 'inglise', ('Õudus',)),
    ('Kapten Krõll', 86, 'PERE', 'eesti', ('Animatsioon', 'Seiklus', 'Komöödia')),
    ('Teine võimalus', 118, 'K-12', 'inglise', ('Draama', 'Romantika')),
    ('Põhjatäht', 137, 'MS-12', 'inglise', ('Seiklus', 'Ulme')),
    ('Kontoriromaan', 95, 'MS-6', 'eesti', ('Komöödia',)),
    ('Varjude linn', 124, 'K-14', 'inglise', ('Krimi', 'Draama')),
    ('Läänemere hüljes', 74, 'PERE', 'eesti', ('Dokumentaal',)),
]

BASE_PRICES = {'2D': Decimal('8.50'), '3D': Decimal('10.50'), 'IMAX': Decimal('13.50')}

REVIEW_COMMENTS = {
    1: ('Kahjuks pettumus, lugu ei haaranud.', 'Liiga venitatud, lahkusin vaheajal peaaegu.'),
    2: ('Mõned head hetked, aga tervikuna nõrk.', 'Näitlejad olid toredad, stsenaarium mitte.'),
    3: ('Korralik film, aga midagi jäi puudu.', 'Sobib ühekordseks vaatamiseks.'),
    4: ('Väga hea film, soovitan sõpradele.', 'Ilus pilt ja hea muusika.'),
    5: ('Suurepärane! Vaataksin kohe uuesti.', 'Selle aasta parim film, mida näinud olen.'),
}


def ascii_slug(text):
    """Teeb nimest kasutajanimeks sobiva ASCII-kuju (Õie → oie)."""
    normalized = unicodedata.normalize('NFKD', text.lower())
    return ''.join(char for char in normalized if char.isascii() and char.isalnum())


def round_up_to_quarter(moment):
    """Ümardab aja üles järgmise veerandtunnini, nagu kinokavas."""
    extra = (15 - moment.minute % 15) % 15
    return moment.replace(second=0, microsecond=0) + timedelta(minutes=extra)


class Command(BaseCommand):
    help = 'Loo Fakeri abil omavahel seotud kinoandmebaasi demoandmed.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Tühjenda kinotabelid (TRUNCATE ... RESTART IDENTITY) enne demoandmete loomist.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        self.fake = Faker('et_EE')
        self.fake.seed_instance(SEED)
        self.rng = random.Random(SEED)
        self.now = timezone.now()

        if options['clear']:
            self.clear_tables()
        elif any(model.objects.exists() for model in (User, Cinema, Movie, Genre, Screening, Booking)):
            raise CommandError(
                'Kinoandmebaas pole tühi. Olemasolevate andmete asendamiseks käivita käsuga --clear.'
            )

        # Järjekord järgib võõrvõtmeid: enne luuakse read, millele hiljem viidatakse.
        users = self.create_users()
        halls = self.create_cinemas_halls_and_seats()
        movies = self.create_genres_and_movies()
        screenings = self.create_screenings(halls, movies)
        bookings = self.create_bookings_and_tickets(screenings, users)
        self.create_payments(bookings)
        self.create_reviews(bookings)

        self.stdout.write(self.style.SUCCESS('Demoandmed loodud:'))
        for model in (User, Cinema, CinemaHall, Seat, Genre, Movie, MovieGenre,
                      Screening, Booking, BookedSeat, Payment, Review):
            self.stdout.write(f'  {model._meta.db_table:<18} {model.objects.count():>6}')

    def clear_tables(self):
        models = (Review, Payment, BookedSeat, Booking, Screening, MovieGenre,
                  Movie, Genre, Seat, CinemaHall, Cinema, User)
        tables = ', '.join(connection.ops.quote_name(model._meta.db_table) for model in models)
        with connection.cursor() as cursor:
            # Django loob võõrvõtmed DEFERRABLE kujul; ootel kontrollid tuleb enne TRUNCATE'i ära teha.
            cursor.execute('SET CONSTRAINTS ALL IMMEDIATE')
            cursor.execute(f'TRUNCATE {tables} RESTART IDENTITY CASCADE')

    def create_users(self):
        # Demokasutajad ei saa sisse logida: parooliräsi on Django "kasutamatu parool".
        password_hash = make_password(None)
        users = []
        for index in range(1, USER_COUNT + 1):
            first_name = self.fake.first_name()
            last_name = self.fake.last_name()
            username = f'{ascii_slug(first_name)}.{ascii_slug(last_name)}{index:02}'
            users.append(User(
                username=username,
                first_name=first_name,
                last_name=last_name,
                phone_number=f'+372 5{self.rng.randrange(10**6, 10**7)}',
                email=f'{username}@example.com',
                date_of_birth=self.fake.date_of_birth(minimum_age=16, maximum_age=75),
                password_hash=password_hash,
            ))
        return User.objects.bulk_create(users)

    def create_cinemas_halls_and_seats(self):
        halls = []
        for name, city, postcode_prefix, hall_specs in CINEMAS:
            cinema = Cinema.objects.create(
                name=name,
                street_address=self.fake.street_address(),
                city=city,
                postal_code=f'{postcode_prefix}{self.rng.randrange(100, 1000)}',
                country='Eesti',
            )
            for hall_name, screen_type, rows, seats_per_row in hall_specs:
                hall = CinemaHall.objects.create(
                    cinema=cinema,
                    name=hall_name,
                    screen_type=screen_type,
                    capacity=rows * seats_per_row,
                )
                hall.seat_list = Seat.objects.bulk_create(
                    Seat(hall=hall, row=str(row), number=number)
                    for row in range(1, rows + 1)
                    for number in range(1, seats_per_row + 1)
                )
                halls.append(hall)
        return halls

    def create_genres_and_movies(self):
        genres = {genre.name: genre for genre in Genre.objects.bulk_create(Genre(name=name) for name in GENRES)}
        movies = []
        links = []
        for title, duration, age_rating, language, genre_names in MOVIES:
            movie = Movie.objects.create(
                title=title,
                description=self.fake.paragraph(nb_sentences=3),
                duration=duration,
                release_date=self.fake.date_between(start_date='-120d', end_date='+10d'),
                age_rating=age_rating,
                language=language,
                is_featured=self.rng.random() < 0.25,
            )
            movie.quality = self.rng.uniform(2.3, 4.6)
            movies.append(movie)
            links.extend(MovieGenre(movie=movie, genre=genres[name]) for name in genre_names)
        MovieGenre.objects.bulk_create(links)
        return movies

    def create_screenings(self, halls, movies):
        today = timezone.localdate()
        screenings = []
        for day_offset in range(-DAYS_BEFORE_TODAY, DAYS_AFTER_TODAY + 1):
            day = today + timedelta(days=day_offset)
            for hall_index, hall in enumerate(halls):
                # Saalid alustavad nihkega, et kassas ei tekiks korraga järjekorda.
                start = timezone.make_aware(datetime.combine(day, time(11, 0))) + timedelta(minutes=15 * (hall_index % 3))
                last_start = timezone.make_aware(datetime.combine(day, time(22, 0)))
                while start <= last_start:
                    movie = self.pick_movie(movies, hall, start)
                    end = start + timedelta(minutes=movie.duration + 15)  # 15 min reklaame
                    screenings.append(Screening(
                        movie=movie,
                        hall=hall,
                        start_time=start,
                        end_time=end,
                        language=movie.language,
                        subtitles=self.pick_subtitles(movie),
                        base_price=self.ticket_price(hall, start),
                    ))
                    start = round_up_to_quarter(end + timedelta(minutes=15))  # koristus
        return Screening.objects.bulk_create(screenings)

    def pick_movie(self, movies, hall, start):
        # Lastefilme näidatakse päeval, õudusfilme ja K-16 filme õhtul.
        if start.astimezone(timezone.get_current_timezone()).hour < 16:
            pool = [movie for movie in movies if movie.age_rating != 'K-16']
        else:
            pool = [movie for movie in movies if movie.age_rating != 'PERE']
        if hall.screen_type == 'IMAX':
            pool = [movie for movie in pool if movie.duration >= 95] or pool
        return self.rng.choice(pool)

    def pick_subtitles(self, movie):
        if movie.language == 'eesti':
            return self.rng.choice(('inglise', None))
        return self.rng.choice(('eesti', 'eesti', 'eesti/vene'))

    def ticket_price(self, hall, start):
        local = start.astimezone(timezone.get_current_timezone())
        price = BASE_PRICES[hall.screen_type]
        if local.hour < 16:
            price -= Decimal('2.00')  # päevaseanss
        if local.weekday() >= 5:
            price += Decimal('1.00')  # nädalavahetus
        return price

    def create_bookings_and_tickets(self, screenings, users):
        bookings = []
        tickets_by_booking = []
        for screening in screenings:
            free_rows = {}
            for seat in screening.hall.seat_list:
                free_rows.setdefault(seat.row, []).append(seat)

            for _ in range(self.rng.randint(0, 5)):
                seats = self.pick_adjacent_seats(free_rows, self.rng.choice((1, 2, 2, 2, 3, 4)))
                if not seats:
                    continue
                created_at = self.booking_time(screening)
                bookings.append(Booking(
                    user=self.rng.choice(users),
                    screening=screening,
                    status=self.booking_status(screening, created_at),
                    total=screening.base_price * len(seats),
                    created_at=created_at,
                ))
                tickets_by_booking.append(seats)

        Booking.objects.bulk_create(bookings)
        BookedSeat.objects.bulk_create(
            BookedSeat(booking=booking, screening=booking.screening, seat=seat, price=booking.screening.base_price)
            for booking, seats in zip(bookings, tickets_by_booking)
            for seat in seats
        )
        return bookings

    def pick_adjacent_seats(self, free_rows, count):
        """Valib ühest reast järjestikused vabad kohad ja märgib need hõivatuks."""
        rows = list(free_rows)
        self.rng.shuffle(rows)
        for row in rows:
            seats = free_rows[row]
            for start in range(len(seats) - count + 1):
                block = seats[start:start + count]
                if block[-1].number - block[0].number == count - 1:
                    free_rows[row] = seats[:start] + seats[start + count:]
                    return block
        return None

    def booking_time(self, screening):
        # Broneering tehakse enne seansi algust ega saa olla tulevikus.
        created_at = screening.start_time - timedelta(minutes=self.rng.randint(20, 9 * 24 * 60))
        if created_at > self.now:
            created_at = self.now - timedelta(minutes=self.rng.randint(5, 6 * 60))
        return created_at

    def booking_status(self, screening, created_at):
        roll = self.rng.random()
        if roll < 0.12:
            return 'tühistatud'
        # Ootel saab olla ainult tulevase seansi värske broneering.
        if screening.start_time > self.now and self.now - created_at < timedelta(hours=2) and roll < 0.5:
            return 'ootel'
        return 'kinnitatud'

    def create_payments(self, bookings):
        payments = []
        for booking in bookings:
            method = self.rng.choice(('kaart', 'kaart', 'pangalink', 'mobiilimakse'))
            paid_at = min(self.now, booking.created_at + timedelta(minutes=self.rng.randint(1, 10)))
            if booking.status == 'kinnitatud':
                if self.rng.random() < 0.1:
                    # Esimene katse ebaõnnestus, teine õnnestus – näitab seost 1:N.
                    payments.append(self.payment(booking, method, 'ebaõnnestunud', None))
                payments.append(self.payment(booking, method, 'edukas', paid_at))
            elif booking.status == 'ootel':
                payments.append(self.payment(booking, method, 'ootel', None))
            elif self.rng.random() < 0.5:
                payments.append(self.payment(booking, method, 'tagastatud', paid_at))
            else:
                payments.append(self.payment(booking, method, 'ebaõnnestunud', None))
        Payment.objects.bulk_create(payments)

    def payment(self, booking, method, status, paid_at):
        return Payment(
            booking=booking,
            amount=booking.total,
            method=method,
            status=status,
            reference=str(self.fake.uuid4()),
            paid_at=paid_at,
        )

    def create_reviews(self, bookings):
        # Arvustuse kirjutab ainult kasutaja, kes on filmi kinnitatud broneeringuga juba näinud.
        reviewed = set()
        reviews = []
        for booking in bookings:
            screening = booking.screening
            key = (booking.user_id, screening.movie_id)
            if booking.status != 'kinnitatud' or screening.end_time > self.now or key in reviewed:
                continue
            if self.rng.random() > 0.35:
                continue
            reviewed.add(key)
            rating = min(5, max(1, round(self.rng.gauss(screening.movie.quality, 0.9))))
            created_at = min(self.now, screening.end_time + timedelta(hours=self.rng.randint(1, 72)))
            reviews.append(Review(
                user_id=booking.user_id,
                movie_id=screening.movie_id,
                rating=rating,
                comment=self.rng.choice(REVIEW_COMMENTS[rating]),
                created_at=created_at,
            ))
        Review.objects.bulk_create(reviews)
