"""
Tests for the High School Management System API
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state
    original_activities = {
        name: {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
        for name, details in activities.items()
    }
    
    yield
    
    # Restore original state after test
    for name, details in original_activities.items():
        activities[name]["participants"] = details["participants"].copy()


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root redirects to static index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that GET /activities returns all activities"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, dict)
        assert len(data) > 0
        assert "Soccer Team" in data
        assert "Basketball Club" in data
    
    def test_activities_have_required_fields(self, client):
        """Test that each activity has required fields"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_details in data.items():
            assert "description" in activity_details
            assert "schedule" in activity_details
            assert "max_participants" in activity_details
            assert "participants" in activity_details
            assert isinstance(activity_details["participants"], list)


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_new_participant_success(self, client):
        """Test successful signup of a new participant"""
        response = client.post(
            "/activities/Soccer Team/signup?email=newstudent@mergington.edu"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "newstudent@mergington.edu" in data["message"]
        
        # Verify student was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert "newstudent@mergington.edu" in activities_data["Soccer Team"]["participants"]
    
    def test_signup_duplicate_participant_fails(self, client):
        """Test that duplicate signup fails"""
        email = "lucas@mergington.edu"
        
        # This student is already signed up for Soccer Team
        response = client.post(f"/activities/Soccer Team/signup?email={email}")
        assert response.status_code == 400
        data = response.json()
        assert "already signed up" in data["detail"].lower()
    
    def test_signup_nonexistent_activity_fails(self, client):
        """Test that signup for non-existent activity fails"""
        response = client.post(
            "/activities/Nonexistent Activity/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_signup_full_activity_fails(self, client):
        """Test that signup fails when activity is full"""
        # First, fill up the Science Club (max 14 participants)
        science_club = activities["Science Club"]
        original_participants = science_club["participants"].copy()
        
        # Add participants until full
        for i in range(science_club["max_participants"] - len(original_participants)):
            science_club["participants"].append(f"student{i}@mergington.edu")
        
        # Try to add one more
        response = client.post(
            "/activities/Science Club/signup?email=overflow@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "full" in data["detail"].lower()


class TestUnregisterFromActivity:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_existing_participant_success(self, client):
        """Test successful unregistration of an existing participant"""
        email = "lucas@mergington.edu"
        
        # Verify student is initially signed up
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email in activities_data["Soccer Team"]["participants"]
        
        # Unregister
        response = client.delete(f"/activities/Soccer Team/unregister?email={email}")
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert email in data["message"]
        
        # Verify student was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email not in activities_data["Soccer Team"]["participants"]
    
    def test_unregister_non_registered_participant_fails(self, client):
        """Test that unregistering a non-registered participant fails"""
        response = client.delete(
            "/activities/Soccer Team/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "not registered" in data["detail"].lower()
    
    def test_unregister_from_nonexistent_activity_fails(self, client):
        """Test that unregister from non-existent activity fails"""
        response = client.delete(
            "/activities/Nonexistent Activity/unregister?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()
    
    def test_unregister_then_signup_again(self, client):
        """Test that a student can signup again after unregistering"""
        email = "lucas@mergington.edu"
        activity = "Soccer Team"
        
        # Unregister
        response = client.delete(f"/activities/{activity}/unregister?email={email}")
        assert response.status_code == 200
        
        # Sign up again
        response = client.post(f"/activities/{activity}/signup?email={email}")
        assert response.status_code == 200
        
        # Verify student is back
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert email in activities_data[activity]["participants"]


class TestIntegration:
    """Integration tests for complete workflows"""
    
    def test_complete_signup_unregister_workflow(self, client):
        """Test complete workflow: get activities, signup, verify, unregister"""
        email = "integrationtest@mergington.edu"
        activity = "Drama Club"
        
        # Get initial activities
        response = client.get("/activities")
        assert response.status_code == 200
        initial_data = response.json()
        initial_count = len(initial_data[activity]["participants"])
        
        # Signup
        response = client.post(f"/activities/{activity}/signup?email={email}")
        assert response.status_code == 200
        
        # Verify signup
        response = client.get("/activities")
        data = response.json()
        assert email in data[activity]["participants"]
        assert len(data[activity]["participants"]) == initial_count + 1
        
        # Unregister
        response = client.delete(f"/activities/{activity}/unregister?email={email}")
        assert response.status_code == 200
        
        # Verify unregistration
        response = client.get("/activities")
        data = response.json()
        assert email not in data[activity]["participants"]
        assert len(data[activity]["participants"]) == initial_count
