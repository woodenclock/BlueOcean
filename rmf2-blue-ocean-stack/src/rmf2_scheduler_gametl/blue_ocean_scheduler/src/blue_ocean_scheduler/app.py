# Copyright 2024-2026 ROS Industrial Consortium Asia Pacific
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from contextlib import asynccontextmanager

from demo_routes.blue_ocean import build_demo_description
from demo_routes.blue_ocean import router as blue_ocean_router
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from rmf2_scheduler import SchedulerOptions
from rmf2_scheduler.fastapi import scheduler_api_router
from rmf2_scheduler.fastapi.scheduler import make_scheduler
from rmf2_scheduler.storage import ScheduleStream


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Define startup and shutdown actions."""
    print("Starting Scheduler")

    with make_scheduler(
        SchedulerOptions(),
        ScheduleStream.create_simple(5, "~/.cache/r2ts-backups"),
        None,
        None,
    ):
        yield


app = FastAPI(
    title="RMF2 Task Scheduler Service",
    description=build_demo_description(),
    lifespan=lifespan,
    openapi_tags=[
        {"name": "Demo", "description": "Blue Ocean demo endpoints."},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(blue_ocean_router)
app.include_router(scheduler_api_router)
