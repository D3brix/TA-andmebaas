from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError, transaction
from django.db.models import Count, F, Sum
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from cinema.models import (
    BookedSeat,
    Booking,
    CinemaHall,
    Movie,
    MovieGenre,
    Payment,
    Review,
    Screening,
    Seat,
    User,
)


class HealthViewTests(SimpleTestCase):
    def test_health_endpoint_returns_app_status(self):
        response = self.client.get(reverse('cinema:health'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            'app': 'cinema',
            'status': 'ok',
        })


class SeedDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', stdout=StringIO())

    def test_large_tables_have_at_least_100_rows(self):
        for model in (Screening, Booking, BookedSeat, Payment, Review):
            with self.subTest(model=model.__name__):
                self.assertGreaterEqual(model.objects.count(), 100)

    def test_every_movie_has_a_genre(self):
        self.assertFalse(Movie.objects.annotate(n=Count('genres')).filter(n=0).exists())
        self.assertGreater(MovieGenre.objects.count(), Movie.objects.count())

    def test_ticket_belongs_to_booking_screening_and_hall(self):
        self.assertFalse(BookedSeat.objects.exclude(screening=F('booking__screening')).exists())
        self.assertFalse(BookedSeat.objects.exclude(seat__hall=F('screening__hall')).exists())

    def test_hall_capacity_matches_seats(self):
        for hall in CinemaHall.objects.annotate(n=Count('seats')):
            self.assertEqual(hall.capacity, hall.n)

    def test_booking_total_matches_tickets(self):
        for booking in Booking.objects.annotate(tickets=Sum('booked_seats__price')):
            self.assertEqual(booking.total, booking.tickets)

    def test_booking_is_made_before_screening(self):
        self.assertFalse(Booking.objects.filter(created_at__gt=F('screening__start_time')).exists())

    def test_payment_status_matches_booking_status(self):
        confirmed_without_payment = Booking.objects.filter(status='kinnitatud').exclude(payments__status='edukas')
        self.assertFalse(confirmed_without_payment.exists())
        self.assertFalse(Payment.objects.filter(booking__status='tühistatud', status='edukas').exists())

    def test_reviews_only_from_viewers(self):
        for review in Review.objects.all():
            self.assertTrue(Booking.objects.filter(
                user=review.user, screening__movie=review.movie, status='kinnitatud',
            ).exists())

    def test_seeder_refuses_non_empty_database(self):
        with self.assertRaises(CommandError):
            call_command('seed_demo')

    def test_seeder_clear_is_repeatable(self):
        counts = {model: model.objects.count() for model in (User, Seat, Screening, Booking, BookedSeat)}
        call_command('seed_demo', '--clear', stdout=StringIO())
        for model, count in counts.items():
            with self.subTest(model=model.__name__):
                self.assertEqual(model.objects.count(), count)
        self.assertEqual(User.objects.order_by('id').first().id, 1)


class ConstraintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('seed_demo', stdout=StringIO())

    def assertRejected(self, create):
        with self.assertRaises(IntegrityError), transaction.atomic():
            create()

    def test_overlapping_screening_in_same_hall_is_rejected(self):
        existing = Screening.objects.first()
        self.assertRejected(lambda: Screening.objects.create(
            movie=existing.movie,
            hall=existing.hall,
            start_time=existing.start_time + timedelta(minutes=30),
            end_time=existing.end_time + timedelta(minutes=30),
            base_price=Decimal('9.00'),
        ))

    def test_screening_must_end_after_start(self):
        existing = Screening.objects.first()
        self.assertRejected(lambda: Screening.objects.create(
            movie=existing.movie,
            hall=existing.hall,
            start_time=existing.start_time - timedelta(days=30),
            end_time=existing.start_time - timedelta(days=31),
            base_price=Decimal('9.00'),
        ))

    def test_same_seat_cannot_be_sold_twice(self):
        ticket = BookedSeat.objects.first()
        self.assertRejected(lambda: BookedSeat.objects.create(
            booking=ticket.booking, screening=ticket.screening, seat=ticket.seat, price=ticket.price,
        ))

    def test_review_rating_must_be_1_to_5(self):
        review = Review.objects.first()
        Review.objects.filter(pk=review.pk).delete()
        self.assertRejected(lambda: Review.objects.create(user=review.user, movie=review.movie, rating=6))

    def test_user_can_review_movie_once(self):
        review = Review.objects.first()
        self.assertRejected(lambda: Review.objects.create(user=review.user, movie=review.movie, rating=3))

    def test_duplicate_email_is_rejected(self):
        user = User.objects.first()
        self.assertRejected(lambda: User.objects.create(
            username='uus.kasutaja', first_name='Uus', last_name='Kasutaja',
            phone_number='+372 5000000', email=user.email, password_hash='!',
        ))
