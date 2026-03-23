from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from ..schemas.packet import HistoricalPacket
from ..schemas.readiness_v2 import (
    ReadinessV2BootstrapArtifact,
    ReadinessV2ReplayArtifact,
    ReadinessV2UpdateArtifact,
    ReadinessWatchV1,
)
from .cl import (
    build_cl_initial_query_triggers,
    build_cl_initial_readiness_watch,
    build_cl_premarket_briefing,
    replay_cl_readiness_sequence,
    update_cl_readiness_watch,
)
from .es import (
    build_es_initial_query_triggers,
    build_es_initial_readiness_watch,
    build_es_premarket_briefing,
    replay_es_readiness_sequence,
    update_es_readiness_watch,
)
from .mgc import (
    build_mgc_initial_query_triggers,
    build_mgc_initial_readiness_watch,
    build_mgc_premarket_briefing,
    replay_mgc_readiness_sequence,
    update_mgc_readiness_watch,
)
from .nq import (
    build_nq_initial_query_triggers,
    build_nq_initial_readiness_watch,
    build_nq_premarket_briefing,
    replay_nq_readiness_sequence,
    update_nq_readiness_watch,
)
from .sixe import (
    build_sixe_initial_query_triggers,
    build_sixe_initial_readiness_watch,
    build_sixe_premarket_briefing,
    replay_sixe_readiness_sequence,
    update_sixe_readiness_watch,
)
from .zn import (
    build_zn_initial_query_triggers,
    build_zn_initial_readiness_watch,
    build_zn_premarket_briefing,
    replay_zn_readiness_sequence,
    update_zn_readiness_watch,
)


class ReadinessV2ContractAdapter(Protocol):
    contract: str

    def bootstrap(
        self,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime | None = None,
    ) -> ReadinessV2BootstrapArtifact: ...

    def update(
        self,
        prior_watch: ReadinessWatchV1,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime,
    ) -> ReadinessV2UpdateArtifact: ...

    def replay(
        self,
        packet: HistoricalPacket,
        updates: Sequence[Mapping[str, Any]],
        *,
        bootstrap_evaluation_time: datetime | None = None,
    ) -> ReadinessV2ReplayArtifact: ...


def _build_bootstrap_artifact(
    *,
    contract: str,
    packet: HistoricalPacket,
    evaluation_timestamp: datetime | None,
    build_briefing,
    build_query_triggers,
    build_watch,
) -> ReadinessV2BootstrapArtifact:
    briefing = build_briefing(packet, created_at=evaluation_timestamp)
    query_triggers = build_query_triggers(packet, briefing)
    watch = build_watch(
        packet,
        briefing,
        query_triggers,
        evaluation_time=briefing.created_at,
    )
    return ReadinessV2BootstrapArtifact(
        contract=contract,
        evaluation_timestamp=briefing.created_at,
        briefing=briefing,
        query_triggers=query_triggers,
        watch=watch,
    )


def _build_update_artifact(
    *,
    contract: str,
    prior_watch: ReadinessWatchV1,
    packet: HistoricalPacket,
    evaluation_timestamp: datetime,
    update_watch,
) -> ReadinessV2UpdateArtifact:
    watch = update_watch(
        prior_watch,
        packet,
        evaluation_timestamp=evaluation_timestamp,
    )
    return ReadinessV2UpdateArtifact(
        contract=contract,
        evaluation_timestamp=evaluation_timestamp,
        prior_watch_id=prior_watch.watch_id,
        watch=watch,
    )


@dataclass(frozen=True)
class ZNReadinessV2ContractAdapter:
    contract: str = "ZN"

    def bootstrap(
        self,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime | None = None,
    ) -> ReadinessV2BootstrapArtifact:
        return _build_bootstrap_artifact(
            contract=self.contract,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            build_briefing=build_zn_premarket_briefing,
            build_query_triggers=build_zn_initial_query_triggers,
            build_watch=build_zn_initial_readiness_watch,
        )

    def update(
        self,
        prior_watch: ReadinessWatchV1,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime,
    ) -> ReadinessV2UpdateArtifact:
        return _build_update_artifact(
            contract=self.contract,
            prior_watch=prior_watch,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            update_watch=update_zn_readiness_watch,
        )

    def replay(
        self,
        packet: HistoricalPacket,
        updates: Sequence[Mapping[str, Any]],
        *,
        bootstrap_evaluation_time: datetime | None = None,
    ) -> ReadinessV2ReplayArtifact:
        return replay_zn_readiness_sequence(
            packet,
            updates,
            bootstrap_evaluation_time=bootstrap_evaluation_time,
        )


@dataclass(frozen=True)
class ESReadinessV2ContractAdapter:
    contract: str = "ES"

    def bootstrap(
        self,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime | None = None,
    ) -> ReadinessV2BootstrapArtifact:
        return _build_bootstrap_artifact(
            contract=self.contract,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            build_briefing=build_es_premarket_briefing,
            build_query_triggers=build_es_initial_query_triggers,
            build_watch=build_es_initial_readiness_watch,
        )

    def update(
        self,
        prior_watch: ReadinessWatchV1,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime,
    ) -> ReadinessV2UpdateArtifact:
        return _build_update_artifact(
            contract=self.contract,
            prior_watch=prior_watch,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            update_watch=update_es_readiness_watch,
        )

    def replay(
        self,
        packet: HistoricalPacket,
        updates: Sequence[Mapping[str, Any]],
        *,
        bootstrap_evaluation_time: datetime | None = None,
    ) -> ReadinessV2ReplayArtifact:
        return replay_es_readiness_sequence(
            packet,
            updates,
            bootstrap_evaluation_time=bootstrap_evaluation_time,
        )


@dataclass(frozen=True)
class NQReadinessV2ContractAdapter:
    contract: str = "NQ"

    def bootstrap(
        self,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime | None = None,
    ) -> ReadinessV2BootstrapArtifact:
        return _build_bootstrap_artifact(
            contract=self.contract,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            build_briefing=build_nq_premarket_briefing,
            build_query_triggers=build_nq_initial_query_triggers,
            build_watch=build_nq_initial_readiness_watch,
        )

    def update(
        self,
        prior_watch: ReadinessWatchV1,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime,
    ) -> ReadinessV2UpdateArtifact:
        return _build_update_artifact(
            contract=self.contract,
            prior_watch=prior_watch,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            update_watch=update_nq_readiness_watch,
        )

    def replay(
        self,
        packet: HistoricalPacket,
        updates: Sequence[Mapping[str, Any]],
        *,
        bootstrap_evaluation_time: datetime | None = None,
    ) -> ReadinessV2ReplayArtifact:
        return replay_nq_readiness_sequence(
            packet,
            updates,
            bootstrap_evaluation_time=bootstrap_evaluation_time,
        )


@dataclass(frozen=True)
class CLReadinessV2ContractAdapter:
    contract: str = "CL"

    def bootstrap(
        self,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime | None = None,
    ) -> ReadinessV2BootstrapArtifact:
        return _build_bootstrap_artifact(
            contract=self.contract,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            build_briefing=build_cl_premarket_briefing,
            build_query_triggers=build_cl_initial_query_triggers,
            build_watch=build_cl_initial_readiness_watch,
        )

    def update(
        self,
        prior_watch: ReadinessWatchV1,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime,
    ) -> ReadinessV2UpdateArtifact:
        return _build_update_artifact(
            contract=self.contract,
            prior_watch=prior_watch,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            update_watch=update_cl_readiness_watch,
        )

    def replay(
        self,
        packet: HistoricalPacket,
        updates: Sequence[Mapping[str, Any]],
        *,
        bootstrap_evaluation_time: datetime | None = None,
    ) -> ReadinessV2ReplayArtifact:
        return replay_cl_readiness_sequence(
            packet,
            updates,
            bootstrap_evaluation_time=bootstrap_evaluation_time,
        )


@dataclass(frozen=True)
class MGCReadinessV2ContractAdapter:
    contract: str = "MGC"

    def bootstrap(
        self,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime | None = None,
    ) -> ReadinessV2BootstrapArtifact:
        return _build_bootstrap_artifact(
            contract=self.contract,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            build_briefing=build_mgc_premarket_briefing,
            build_query_triggers=build_mgc_initial_query_triggers,
            build_watch=build_mgc_initial_readiness_watch,
        )

    def update(
        self,
        prior_watch: ReadinessWatchV1,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime,
    ) -> ReadinessV2UpdateArtifact:
        return _build_update_artifact(
            contract=self.contract,
            prior_watch=prior_watch,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            update_watch=update_mgc_readiness_watch,
        )

    def replay(
        self,
        packet: HistoricalPacket,
        updates: Sequence[Mapping[str, Any]],
        *,
        bootstrap_evaluation_time: datetime | None = None,
    ) -> ReadinessV2ReplayArtifact:
        return replay_mgc_readiness_sequence(
            packet,
            updates,
            bootstrap_evaluation_time=bootstrap_evaluation_time,
        )


@dataclass(frozen=True)
class SixEReadinessV2ContractAdapter:
    contract: str = "6E"

    def bootstrap(
        self,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime | None = None,
    ) -> ReadinessV2BootstrapArtifact:
        return _build_bootstrap_artifact(
            contract=self.contract,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            build_briefing=build_sixe_premarket_briefing,
            build_query_triggers=build_sixe_initial_query_triggers,
            build_watch=build_sixe_initial_readiness_watch,
        )

    def update(
        self,
        prior_watch: ReadinessWatchV1,
        packet: HistoricalPacket,
        *,
        evaluation_timestamp: datetime,
    ) -> ReadinessV2UpdateArtifact:
        return _build_update_artifact(
            contract=self.contract,
            prior_watch=prior_watch,
            packet=packet,
            evaluation_timestamp=evaluation_timestamp,
            update_watch=update_sixe_readiness_watch,
        )

    def replay(
        self,
        packet: HistoricalPacket,
        updates: Sequence[Mapping[str, Any]],
        *,
        bootstrap_evaluation_time: datetime | None = None,
    ) -> ReadinessV2ReplayArtifact:
        return replay_sixe_readiness_sequence(
            packet,
            updates,
            bootstrap_evaluation_time=bootstrap_evaluation_time,
        )


_CONTRACT_ADAPTERS: dict[str, ReadinessV2ContractAdapter] = {
    "6E": SixEReadinessV2ContractAdapter(),
    "CL": CLReadinessV2ContractAdapter(),
    "ES": ESReadinessV2ContractAdapter(),
    "MGC": MGCReadinessV2ContractAdapter(),
    "NQ": NQReadinessV2ContractAdapter(),
    "ZN": ZNReadinessV2ContractAdapter(),
}


def get_contract_adapter(contract: str) -> ReadinessV2ContractAdapter:
    try:
        return _CONTRACT_ADAPTERS[contract]
    except KeyError as exc:
        raise ValueError(f"Unsupported readiness v2 contract: {contract}") from exc


def supported_contracts() -> tuple[str, ...]:
    return tuple(sorted(_CONTRACT_ADAPTERS))
