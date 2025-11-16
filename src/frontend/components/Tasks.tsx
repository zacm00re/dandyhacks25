import React, { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";

interface Task {
  title: string;
  notes: string;
  date: string;
}

export default function Tasks() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTasks();
  }, []);

  const fetchTasks = async () => {
    try {
      setLoading(true);

      // Get access token from your auth system
      const access_token = localStorage.getItem("google_access_token"); // Adjust based on your auth implementation

      if (!access_token) {
        throw new Error("No access token found. Please log in.");
      }

      const response = await fetch("http://localhost:7878/api/get_tasks", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          access_token: access_token,
          look_ahead_days: 7, // Optional: customize the number of days to look ahead
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch tasks");
      }

      const data = await response.json();

      if (data.error) {
        throw new Error(data.error);
      }

      setTasks(data);
      setError(null);
    } catch (err: any) {
      setError(err.message);
      // Fallback to mock data for demonstration
      setTasks([
        {
          title: "Complete project proposal",
          notes: "Include budget breakdown and timeline",
          date: "2025-11-16",
        },
        {
          title: "Review pull requests",
          notes: "Focus on the authentication module updates",
          date: "2025-11-17",
        },
        {
          title: "Prepare presentation slides",
          notes: "Client meeting on Thursday - needs charts and demos",
          date: "2025-11-18",
        },
        {
          title: "Update documentation",
          notes: "API endpoints for the new features",
          date: "2025-11-19",
        },
        {
          title: "Team 1:1 meetings",
          notes: "Schedule with all team members for feedback",
          date: "2025-11-20",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateString: string) => {
    const date = new Date(dateString);
    const today = new Date();
    const tomorrow = new Date(today);
    tomorrow.setDate(tomorrow.getDate() + 1);

    // Reset hours for comparison
    today.setHours(0, 0, 0, 0);
    tomorrow.setHours(0, 0, 0, 0);
    const compareDate = new Date(date);
    compareDate.setHours(0, 0, 0, 0);

    if (compareDate.getTime() === today.getTime()) {
      return "Today";
    } else if (compareDate.getTime() === tomorrow.getTime()) {
      return "Tomorrow";
    } else {
      return date.toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      });
    }
  };

  const isOverdue = (dateString: string) => {
    const taskDate = new Date(dateString);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    taskDate.setHours(0, 0, 0, 0);
    return taskDate < today;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="text-lg text-gray-500">Loading tasks...</div>
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
          {tasks.map((task, index) => (
            <Card
              key={index}
              className={`flex-shrink-0 w-80 snap-start hover:shadow-lg transition-shadow ${""}`}
            >
              <CardHeader>
                <CardTitle className="text-lg truncate">{task.title}</CardTitle>
                <CardDescription className="text-sm">
                  <span className={""}>
                    {isOverdue(task.date) && "⚠️ "}
                    {formatDate(task.date)}
                  </span>
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-700 line-clamp-4">
                  {task.notes || "No additional notes"}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {tasks.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          No tasks to display
        </div>
      )}
    </div>
  );
}
