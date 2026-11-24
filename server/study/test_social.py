from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from .models import DistractionInterval, Friendship, GroupMembership, StudyGroup, StudySession

PW = "Study-pass-2026!"


def study(user, minutes, distracted=0, ago_hours=1, open_=False):
    start = timezone.now() - timedelta(hours=ago_hours)
    s = StudySession.objects.create(
        user=user, start_time=start, end_time=None if open_ else start + timedelta(minutes=minutes)
    )
    if distracted:
        DistractionInterval.objects.create(session=s, start_time=start, end_time=start + timedelta(minutes=distracted))
    return s


class SignupTest(TestCase):
    def setUp(self):
        cache.clear()
        self.api = APIClient()

    def test_signup_returns_tokens_and_can_use_api(self):
        res = self.api.post("/api/auth/signup/", {"username": "new_user", "password": PW, "password2": PW}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertIn("access", res.data)
        self.assertTrue(User.objects.get(username="new_user").check_password(PW))

        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {res.data['access']}")
        me = self.api.get("/api/me/")
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.data["username"], "new_user")
        self.assertEqual(me.data["friend_count"], 0)

    def test_signup_validation(self):
        User.objects.create_user("taken", password=PW)
        cases = [
            ({"username": "Taken", "password": PW, "password2": PW}, "이미 사용 중"),
            ({"username": "ab", "password": PW, "password2": PW}, "4~20자"),
            ({"username": "한글아이디", "password": PW, "password2": PW}, "4~20자"),
            ({"username": "gooduser", "password": PW, "password2": PW + "x"}, "일치하지"),
            ({"username": "gooduser", "password": "1234", "password2": "1234"}, None),
        ]
        for body, expected in cases:
            res = self.api.post("/api/auth/signup/", body, format="json")
            self.assertEqual(res.status_code, 400, body)
            if expected:
                self.assertIn(expected, res.data["detail"])
        self.assertFalse(User.objects.filter(username="gooduser").exists())

    def test_signup_throttled(self):
        rates = {"signup": "2/hour", "friend_request": "60/hour", "group_join": "30/hour"}
        with mock.patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates):
            codes = [
                self.api.post("/api/auth/signup/", {"username": f"user{i}x", "password": PW, "password2": PW},
                              format="json").status_code
                for i in range(3)
            ]
        self.assertEqual(codes, [201, 201, 429])

    def test_web_signup(self):
        res = self.client.post("/signup/", {"username": "webuser", "password": PW, "password2": PW})
        self.assertRedirects(res, "/dashboard/")
        res = self.client.get("/dashboard/")
        self.assertContains(res, "webuser")

        self.client.post("/logout/")
        res = self.client.post("/signup/", {"username": "webuser", "password": PW, "password2": PW})
        self.assertContains(res, "이미 사용 중")


class SocialBase(TestCase):
    def setUp(self):
        cache.clear()
        self.me = User.objects.create_user("me_user", password=PW)
        self.alice = User.objects.create_user("alice", password=PW)
        self.bob = User.objects.create_user("bob", password=PW)
        self.api = self.client_for(self.me)

    def client_for(self, user):
        c = APIClient()
        c.force_authenticate(user)
        return c


class FriendTest(SocialBase):
    def test_request_accept_flow(self):
        res = self.api.post("/api/friends/requests/", {"username": "ALICE"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["status"], "pending")

        # 중복 요청
        res = self.api.post("/api/friends/requests/", {"username": "alice"}, format="json")
        self.assertEqual(res.data["status"], "pending")
        self.assertEqual(Friendship.objects.count(), 1)

        alice_api = self.client_for(self.alice)
        received = alice_api.get("/api/friends/requests/").data["received"]
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["user"]["username"], "me_user")

        # 남의 요청은 수락 불가
        req_id = received[0]["id"]
        self.assertEqual(self.client_for(self.bob).post(f"/api/friends/requests/{req_id}/accept/").status_code, 404)
        self.assertEqual(self.api.post(f"/api/friends/requests/{req_id}/accept/").status_code, 404)

        res = alice_api.post(f"/api/friends/requests/{req_id}/accept/")
        self.assertEqual(res.data["status"], "accepted")
        self.assertEqual([f["username"] for f in self.api.get("/api/friends/").data], ["alice"])
        self.assertEqual([f["username"] for f in alice_api.get("/api/friends/").data], ["me_user"])

        res = self.api.post("/api/friends/requests/", {"username": "alice"}, format="json")
        self.assertIn("이미 친구", res.data["detail"])

    def test_mutual_request_auto_accepts(self):
        self.client_for(self.alice).post("/api/friends/requests/", {"username": "me_user"}, format="json")
        res = self.api.post("/api/friends/requests/", {"username": "alice"}, format="json")
        self.assertEqual(res.data["status"], "accepted")
        self.assertEqual(Friendship.objects.get().status, Friendship.ACCEPTED)

    def test_invalid_requests(self):
        self.assertEqual(self.api.post("/api/friends/requests/", {"username": "me_user"}, format="json").status_code, 400)
        self.assertEqual(self.api.post("/api/friends/requests/", {"username": "nobody"}, format="json").status_code, 404)
        self.assertEqual(self.api.post("/api/friends/requests/", {}, format="json").status_code, 400)

    def test_reject_cancel_and_delete(self):
        self.api.post("/api/friends/requests/", {"username": "alice"}, format="json")
        req = Friendship.objects.get()
        self.assertEqual(self.client_for(self.alice).post(f"/api/friends/requests/{req.id}/reject/").status_code, 200)
        self.assertFalse(Friendship.objects.exists())

        self.api.post("/api/friends/requests/", {"username": "bob"}, format="json")
        req = Friendship.objects.get()
        self.assertEqual(self.api.post(f"/api/friends/requests/{req.id}/cancel/").status_code, 200)
        self.assertFalse(Friendship.objects.exists())

        Friendship.objects.create(from_user=self.me, to_user=self.alice, status=Friendship.ACCEPTED)
        self.assertEqual(self.api.delete(f"/api/friends/{self.alice.id}/").status_code, 204)
        self.assertEqual(self.api.delete(f"/api/friends/{self.alice.id}/").status_code, 404)

    def test_friend_ranking(self):
        Friendship.objects.create(from_user=self.me, to_user=self.alice, status=Friendship.ACCEPTED)
        study(self.me, 60, distracted=30)     # 순공부 30분
        study(self.alice, 50)                 # 순공부 50분
        study(self.bob, 300)                  # 친구 아님 → 제외
        study(self.alice, 0, ago_hours=0.25, open_=True)  # 지금 공부 중 (15분)

        res = self.api.get("/api/friends/ranking/?period=today")
        self.assertEqual(res.status_code, 200)
        rows = res.data["ranking"]
        self.assertEqual([r["username"] for r in rows], ["alice", "me_user"])
        self.assertEqual(rows[0]["rank"], 1)
        self.assertTrue(rows[0]["studying_now"])
        self.assertGreaterEqual(rows[0]["focus_seconds"], 65 * 60)
        self.assertEqual(rows[1]["focus_seconds"], 30 * 60)
        self.assertTrue(rows[1]["is_me"])
        self.assertNotIn("image_url", rows[0])

        self.assertEqual(self.api.get("/api/friends/ranking/?period=year").status_code, 400)
        for p in ("today", "week", "month"):
            self.assertEqual(self.api.get(f"/api/friends/ranking/?period={p}").status_code, 200)

    def test_ranking_ties_share_rank(self):
        Friendship.objects.create(from_user=self.me, to_user=self.alice, status=Friendship.ACCEPTED)
        Friendship.objects.create(from_user=self.bob, to_user=self.me, status=Friendship.ACCEPTED)
        study(self.me, 10)
        study(self.alice, 10)
        study(self.bob, 5)
        rows = self.api.get("/api/friends/ranking/?period=today").data["ranking"]
        self.assertEqual([r["rank"] for r in rows], [1, 1, 3])


class GroupTest(SocialBase):
    def create_group(self, api=None, name="알고리즘 스터디"):
        res = (api or self.api).post("/api/groups/", {"name": name, "description": "매일 2시간"}, format="json")
        self.assertEqual(res.status_code, 201)
        return res.data

    def test_create_join_detail_ranking(self):
        group = self.create_group()
        self.assertTrue(group["is_owner"])
        self.assertEqual(len(group["invite_code"]), 8)

        alice_api = self.client_for(self.alice)
        res = alice_api.post("/api/groups/join/", {"invite_code": group["invite_code"].lower()}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["member_count"], 2)
        self.assertFalse(res.data["is_owner"])
        # 재가입은 그대로
        self.assertEqual(alice_api.post("/api/groups/join/", {"invite_code": group["invite_code"]}, format="json").status_code, 200)

        detail = alice_api.get(f"/api/groups/{group['id']}/").data
        self.assertEqual([m["username"] for m in detail["members"]], ["me_user", "alice"])

        study(self.alice, 40)
        study(self.me, 20)
        rows = alice_api.get(f"/api/groups/{group['id']}/ranking/?period=week").data["ranking"]
        self.assertEqual([(r["username"], r["rank"]) for r in rows], [("alice", 1), ("me_user", 2)])

        self.assertEqual([g["name"] for g in alice_api.get("/api/groups/").data], ["알고리즘 스터디"])

    def test_non_member_cannot_see_group(self):
        group = self.create_group()
        bob_api = self.client_for(self.bob)
        self.assertEqual(bob_api.get(f"/api/groups/{group['id']}/").status_code, 404)
        self.assertEqual(bob_api.get(f"/api/groups/{group['id']}/ranking/").status_code, 404)
        self.assertEqual(bob_api.post("/api/groups/join/", {"invite_code": "WRONG123"}, format="json").status_code, 404)

    def test_validation_and_limits(self):
        self.assertEqual(self.api.post("/api/groups/", {"name": "  "}, format="json").status_code, 400)
        self.assertEqual(self.api.post("/api/groups/", {"name": "x" * 31}, format="json").status_code, 400)

        group = StudyGroup.objects.create(name="full", owner=self.alice, invite_code="FULL2345")
        GroupMembership.objects.create(group=group, user=self.alice)
        for i in range(StudyGroup.MAX_MEMBERS - 1):
            GroupMembership.objects.create(group=group, user=User.objects.create_user(f"m{i}", password=PW))
        res = self.api.post("/api/groups/join/", {"invite_code": "FULL2345"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("가득", res.data["detail"])

    def test_owner_leave_transfers_ownership_and_last_leave_deletes(self):
        group = self.create_group()
        alice_api = self.client_for(self.alice)
        alice_api.post("/api/groups/join/", {"invite_code": group["invite_code"]}, format="json")

        self.assertEqual(self.api.post(f"/api/groups/{group['id']}/leave/").status_code, 200)
        self.assertEqual(StudyGroup.objects.get(id=group["id"]).owner, self.alice)

        alice_api.post(f"/api/groups/{group['id']}/leave/")
        self.assertFalse(StudyGroup.objects.filter(id=group["id"]).exists())

    def test_owner_only_actions(self):
        group = self.create_group()
        alice_api = self.client_for(self.alice)
        alice_api.post("/api/groups/join/", {"invite_code": group["invite_code"]}, format="json")

        self.assertEqual(alice_api.post(f"/api/groups/{group['id']}/invite-code/").status_code, 403)
        self.assertEqual(alice_api.delete(f"/api/groups/{group['id']}/").status_code, 403)

        res = self.api.post(f"/api/groups/{group['id']}/invite-code/")
        self.assertNotEqual(res.data["invite_code"], group["invite_code"])
        # 이전 코드는 무효
        bob_api = self.client_for(self.bob)
        self.assertEqual(bob_api.post("/api/groups/join/", {"invite_code": group["invite_code"]}, format="json").status_code, 404)

        self.assertEqual(self.api.delete(f"/api/groups/{group['id']}/").status_code, 204)
        self.assertFalse(StudyGroup.objects.exists())


class DashboardRankingTest(SocialBase):
    def test_dashboard_shows_friend_ranking(self):
        self.client.force_login(self.me)
        self.assertContains(self.client.get("/dashboard/"), "아직 친구가 없습니다")

        Friendship.objects.create(from_user=self.me, to_user=self.alice, status=Friendship.ACCEPTED)
        study(self.alice, 45)
        res = self.client.get("/dashboard/")
        self.assertContains(res, "alice")
        self.assertContains(res, "45분")
