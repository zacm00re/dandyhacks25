import React, { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Sparkles } from "lucide-react";

interface Email {
  id: number;
  sender: string;
  subject: string;
  snippet: string;
  body: string;
  date: any;
  summary: string;
}

export default function Emails() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchEmails();
  }, []);

  const fetchEmails = async () => {
    try {
      setLoading(true);
      // Replace with your actual API endpoint
      const accessToken = localStorage.getItem("google_access_token");
      const response = await fetch("http://localhost:7878/api/get_emails", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          access_token: accessToken,
          days: 2,
        }),
      });

      if (!response.ok) {
        throw new Error("Failed to fetch emails");
      }

      const data = await response.json();
      console.log("098234098234098324");
      console.log(data);
      setEmails(data.emails);
      setError(null);
    } catch (err: any) {
      console.log(err);
      setError(err.message);
      // Fallback to mock data for demonstration
      setEmails([
        {
          id: 1,
          sender: "john@example.com",
          content:
            "Hey! Just wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to fst wanted to follow up on our meeting yesterday. Let me know if you have any questions.",
          date: "2025-11-14",
        },
        {
          id: 2,
          sender: "sarah@company.com",
          content:
            "The quarterly report is ready for review. Please check the attached documents.",
          date: "2025-11-13",
        },
        {
          id: 3,
          sender: "notifications@service.com",
          content:
            "Your subscription will renew on November 20th. Update your payment method if needed.",
          date: "2025-11-12",
        },
        {
          id: 4,
          sender: "team@startup.io",
          content:
            "Congratulations! Your application has been approved. Welcome to the team!",
          date: "2025-11-11",
        },
        {
          id: 5,
          sender: "support@platform.com",
          content:
            "We have received your support ticket. Our team will get back to you within 24 hours.",
          date: "2025-11-10",
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

  if (loading) {
    return (
      <div className="flex items-center justify-center p-4">
        <div className="text-lg text-gray-500">Loading emails...</div>
      </div>
    );
  }

  return (
    <div className="w-full pl-4 ">
      {/*{error && (
        <Alert className="mb-4">
          <AlertDescription>
            Failed to fetch from API. Showing sample data instead.
          </AlertDescription>
        </Alert>
      )}*/}

      <div className="relative">
        <div className="flex gap-4 overflow-x-auto pb-0 snap-x snap-mandatory">
          {emails.map((email) => (
            <Card
              key={email.id}
              className="flex-shrink-0 w-80 snap-start hover:shadow-lg transition-shadow"
            >
              <CardHeader>
                <CardTitle className="text-lg truncate">
                  {email.sender}
                </CardTitle>
                <CardDescription className="text-sm">
                  {formatDate(email.date)}
                </CardDescription>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-gray-700 line-clamp-4">
                  {email.summary}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {emails.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          No emails to display
        </div>
      )}
    </div>
  );
}
