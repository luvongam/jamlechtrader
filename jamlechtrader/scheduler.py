"""Enterprise-grade scheduler for automated trading."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, time as dt_time
from enum import Enum
from typing import Any, Callable

from loguru import logger

from jamlechtrader.core.exceptions import JamlechTraderError


class JobType(Enum):
    """Job execution type."""
    DAILY = "daily"
    INTERVAL = "interval"
    CRON = "cron"


class JobStatus(Enum):
    """Job execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


@dataclass
class Job:
    """Scheduled job configuration."""
    name: str
    job_type: JobType
    func: Callable
    args: tuple = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    run_time: dt_time | None = None
    interval_seconds: int | None = None
    last_run: datetime | None = None
    last_status: JobStatus = JobStatus.PENDING
    error_count: int = 0
    max_retries: int = 3

    def should_run(self, now: datetime) -> bool:
        """Check if job should run."""
        if self.job_type == JobType.DAILY:
            if self.last_run is None or self.last_run.date() < now.date():
                return now.time() >= self.run_time
        elif self.job_type == JobType.INTERVAL:
            if self.last_run is None:
                return True
            elapsed = (now - self.last_run).total_seconds()
            return elapsed >= self.interval_seconds
        return False


class TradingScheduler:
    """Enterprise scheduler for automated trading execution."""

    def __init__(self, check_interval: int = 60) -> None:
        self.jobs: dict[str, Job] = {}
        self.check_interval = check_interval
        self._running = False

    def add_daily_job(
        self,
        name: str,
        run_time: dt_time,
        func: Callable,
        *args,
        **kwargs
    ) -> None:
        """Schedule job to run daily at specific time."""
        if name in self.jobs:
            raise JamlechTraderError(f"Job '{name}' already exists")
        
        self.jobs[name] = Job(
            name=name,
            job_type=JobType.DAILY,
            func=func,
            args=args,
            kwargs=kwargs,
            run_time=run_time,
        )
        logger.info(f"Scheduled daily job '{name}' at {run_time}")

    def add_interval_job(
        self,
        name: str,
        interval_seconds: int,
        func: Callable,
        *args,
        **kwargs
    ) -> None:
        """Schedule job to run at regular intervals."""
        if name in self.jobs:
            raise JamlechTraderError(f"Job '{name}' already exists")
        
        self.jobs[name] = Job(
            name=name,
            job_type=JobType.INTERVAL,
            func=func,
            args=args,
            kwargs=kwargs,
            interval_seconds=interval_seconds,
        )
        logger.info(f"Scheduled interval job '{name}' every {interval_seconds}s")

    def remove_job(self, name: str) -> None:
        """Remove scheduled job."""
        if name in self.jobs:
            del self.jobs[name]
            logger.info(f"Removed job '{name}'")

    def _execute_job(self, job: Job) -> None:
        """Execute a single job with error handling."""
        job.last_status = JobStatus.RUNNING
        
        try:
            logger.info(f"Executing job '{job.name}'")
            job.func(*job.args, **job.kwargs)
            job.last_run = datetime.now()
            job.last_status = JobStatus.SUCCESS
            job.error_count = 0
            logger.info(f"Job '{job.name}' completed successfully")
        except Exception as e:
            job.error_count += 1
            job.last_status = JobStatus.FAILED
            logger.error(f"Job '{job.name}' failed (attempt {job.error_count}/{job.max_retries}): {e}")
            
            if job.error_count >= job.max_retries:
                logger.critical(f"Job '{job.name}' exceeded max retries, removing from schedule")
                self.remove_job(job.name)

    def run(self) -> None:
        """Run scheduler main loop."""
        self._running = True
        logger.info(f"Scheduler started with {len(self.jobs)} jobs")
        
        try:
            while self._running:
                now = datetime.now()
                
                for job in list(self.jobs.values()):
                    if job.should_run(now):
                        self._execute_job(job)
                
                time.sleep(self.check_interval)
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
        finally:
            self._running = False

    def stop(self) -> None:
        """Stop scheduler gracefully."""
        self._running = False
        logger.info("Scheduler stopping...")

    def get_status(self) -> dict[str, Any]:
        """Get scheduler status."""
        return {
            "running": self._running,
            "jobs": {
                name: {
                    "type": job.job_type.value,
                    "last_run": job.last_run.isoformat() if job.last_run else None,
                    "status": job.last_status.value,
                    "error_count": job.error_count,
                }
                for name, job in self.jobs.items()
            },
        }
