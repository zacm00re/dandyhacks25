import React, { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface Event {
  title: string;
  start_time: string;
  end_time: string;
  location: string;
  description: string;
  date: string;
}

export default function Events() {
  const [events, setEvents] = useState<Event[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchEvents();
  }, []);

  const fetchEvents = async () => {
    try {
      setLoading(true);

      // Get access token from your auth system
      const access_token = localStorage.getItem("google_access_token"); // Adjust based on your auth implementation

      if (!access_token) {
        throw new Error("No access token found. Please log in.");
      }

      const response = await fetch("http://localhost:7878/api/get_events", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          access_token: access_token,
          // Optional: customize time range
          // time_min: new Date().toISOString(),
          // time_max: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toISOString(),
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch events");
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      setEvents(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
      // Fallback to mock data for demonstration
      setEvents([
        {
          title: "Team Standup",
          start_time: "09:00",
          end_time: "09:30",
          location: "Conference Room A",
          description: "Daily team sync",
          date: "2025-11-16",
        },
        {
          title: "Client Meeting",
          start_time: "14:00",
          end_time: "15:00",
          location: "Zoom",
          description: "Q4 review with stakeholders",
          date: "2025-11-16",
        },
        {
          title: "Code Review",
          start_time: "11:00",
          end_time: "12:00",
          location: "",
          description: "Review PRs for the new feature",
          date: "2025-11-17",
        },
        {
          title: "All Hands Meeting",
          start_time: "16:00",
          end_time: "17:00",
          location: "Main Auditorium",
          description: "Monthly company update",
          date: "2025-11-18",
        },
        {
          title: "Project Planning",
          start_time: "10:00",
          end_time: "11:30",
          location: "Conference Room B",
          description: "Sprint planning for next iteration",
          date: "2025-11-19",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    return date.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  };

  const formatTime = (time: string) => {
    if (!time) return "";
    // Convert 24h to 12h format
    const [hours, minutes] = time.split(":");
    const hour = parseInt(hours);
    const ampm = hour >= 12 ? "PM" : "AM";
    const hour12 = hour % 12 || 12;
    return `${hour12}:${minutes} ${ampm}`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="text-lg text-gray-500">Loading events...</div>
      </div>
    );
  }

  return (
    <div className="w-full pl-4">
      {/*{error && (
        <Alert className="mb-4">
          <AlertDescription>
            {error}. Showing sample data instead.
          </AlertDescription>
        </Alert>
      )}*/}

      <div className="relative">
        <div className="flex gap-4 overflow-x-auto pb-0 snap-x snap-mandatory scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-gray-100">
          {events.map((event, index) => (
            <Card
              key={index}
              className="flex-shrink-0 w-80 snap-start hover:shadow-lg transition-shadow"
            >
              <CardHeader>
                <CardTitle className="text-lg truncate">
                  {event.title}
                </CardTitle>
                <CardDescription className="text-sm">
                  {formatDate(event.date)}
                  {event.start_time && (
                    <span className="ml-2">
                      {formatTime(event.start_time)}
                      {event.end_time && ` - ${formatTime(event.end_time)}`}
                    </span>
                  )}
                </CardDescription>
              </CardHeader>
              <CardContent>
                {event.location && (
                  <p className="text-sm text-gray-600 mb-2">
                    📍 {event.location}
                  </p>
                )}
                <p className="text-sm text-gray-700 line-clamp-3">
                  {event.description || "No description"}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {events.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          No events to display
        </div>
      )}
    </div>
  );
}
