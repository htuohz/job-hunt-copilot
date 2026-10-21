"use server";

import { revalidatePath } from "next/cache";
import { JOB_STATUSES, setJobStatus, type JobStatus } from "@jhc/core";
import { db } from "@/lib/db";

export async function updateStatus(formData: FormData): Promise<void> {
  const id = Number(formData.get("id"));
  const status = formData.get("status") as JobStatus;
  if (!Number.isInteger(id) || !JOB_STATUSES.includes(status)) {
    throw new Error("Invalid job or status");
  }
  await setJobStatus(db(), id, status);
  revalidatePath("/");
}
