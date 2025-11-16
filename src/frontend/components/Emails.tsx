import React, { useState, useEffect } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Sparkles, Loader2 } from "lucide-react";
import { Button } from "./ui/button";

interface Email {
  id: number;
  sender: string;
  subject: string;
  snippet: string;
  body: string;
  date: any;
  summary: string;
}

async function summarizeEmail(emailBody: string) {
  const response = await fetch("http://localhost:7878/api/summarize_email", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      emailBody: emailBody,
    }),
  });
  if (!response.ok) {
    throw new Error("Failed to summarize email");
  }
  const text = await response.text();
  return text;
}

export default function Emails() {
  const [emails, setEmails] = useState<Email[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [summarizingIds, setSummarizingIds] = useState<Set<number>>(new Set());

  useEffect(() => {
    fetchEmails();
  }, []);

  const fetchEmails = async () => {
    try {
      setLoading(true);
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
      setEmails(data);
      setError(null);
    } catch (err: any) {
      console.log(err);
      setError(err.message);
      setEmails([
        {
          id: 1,
          sender: "john@example.com",
          subject: "Follow up",
          snippet: "Hey! Just wanted to follow up on our meeting yesterday...",
          body: "Hey! Just wanted to follow up on our meeting yesterday. Let me know if you have any questions.",
          date: "2025-11-14",
          summary: "",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleSummarize = async (emailId: number, emailBody: string) => {
    setSummarizingIds((prev) => new Set(prev).add(emailId));

    try {
      const summary = await summarizeEmail(emailBody);

      setEmails((prevEmails) =>
        prevEmails.map((email) =>
          email.id === emailId ? { ...email, summary } : email,
        ),
      );
    } catch (error) {
      console.error("Failed to summarize email:", error);
    } finally {
      setSummarizingIds((prev) => {
        const newSet = new Set(prev);
        newSet.delete(emailId);
        return newSet;
      });
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
      <div className="relative">
        <div className="flex gap-4 overflow-x-auto pb-0 snap-x snap-mandatory">
          {emails.map((email) => {
            const isSummarizing = summarizingIds.has(email.id);
            const hasSummary = !!email.summary;
            const displayText = email.summary || email.snippet;

            return (
              <Card
                key={email.id}
                className="h-full flex-shrink-0 w-80 snap-start hover:shadow-lg transition-shadow"
              >
                <CardHeader className="pb-0">
                  <CardTitle className="text-md truncate">
                    {email.sender}
                  </CardTitle>
                  <CardDescription className="flex justify-between text-sm">
                    {formatDate(email.date)}
                    {!hasSummary && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          handleSummarize(
                            email.id,
                            email.body || email.snippet,
                          );
                        }}
                        disabled={isSummarizing}
                      >
                        {isSummarizing ? (
                          <Loader2 className="animate-spin" color="#1447e6" />
                        ) : (
                          <Sparkles color="#1447e6" />
                        )}
                      </Button>
                    )}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {isSummarizing ? (
                    <div className="flex items-center gap-2 text-sm text-gray-500">
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Generating summary...
                    </div>
                  ) : (
                    <p
                      className={`text-sm line-clamp-4 ${
                        hasSummary
                          ? "text-blue-600 font-medium"
                          : "text-gray-700"
                      }`}
                    >
                      {displayText}
                    </p>
                  )}
                </CardContent>
              </Card>
            );
          })}
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
