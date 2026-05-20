use rmcp::{
    handler::server::{router::tool::ToolRouter, wrapper::Parameters},
    model::*,
    tool, tool_handler,
    ErrorData as McpError, ServerHandler, ServiceExt,
};
use rmcp::service::RequestContext;
use rmcp::RoleServer;
use schemars::JsonSchema;
use serde::Deserialize;
use std::sync::{Arc, Mutex};

#[derive(Debug, Deserialize, JsonSchema)]
pub struct MoveRequest {
    pub azimuth_steps: i32,
    pub elevation_steps: i32,
}

#[derive(Debug, Deserialize, JsonSchema)]
pub struct PositionRequest {}

#[derive(Clone)]
pub struct AntennaServer {
    tool_router: ToolRouter<Self>,
    state: Arc<Mutex<AntennaState>>,
}

#[derive(Default)]
struct AntennaState {
    az: i32,
    el: i32,
}

#[tool_handler]
impl AntennaServer {
    pub fn new() -> Self {
        Self {
            tool_router: ToolRouter::new(),
            state: Arc::new(Mutex::new(AntennaState::default())),
        }
    }

    #[tool(description = "Move the antenna by step counts")]
    fn move_antenna(
        &self,
        Parameters(MoveRequest {
            azimuth_steps,
            elevation_steps,
        }): Parameters<MoveRequest>,
    ) -> Result<CallToolResult, McpError> {
        let mut state = self.state.lock().unwrap();
        state.az += azimuth_steps;
        state.el += elevation_steps;

        Ok(CallToolResult::success(vec![Content::text(format!(
            "Moved. Current position → azimuth: {}, elevation: {}",
            state.az, state.el
        ))]))
    }

    #[tool(description = "Get the current antenna position")]
    fn get_position(
        &self,
        _params: Parameters<PositionRequest>,
    ) -> Result<CallToolResult, McpError> {
        let state = self.state.lock().unwrap();

        Ok(CallToolResult::success(vec![Content::text(format!(
            "Current position → azimuth: {}, elevation: {}",
            state.az, state.el
        ))]))
    }
}

impl ServerHandler for AntennaServer {

    async fn initialize(
        &self,
        _params: InitializeRequestParams,
        _ctx: RequestContext<RoleServer>,
    ) -> Result<InitializeResult, McpError> {
        let capabilities = ServerCapabilities::builder()
            .enable_tools()
            .build();

        let mut result = InitializeResult::new(capabilities);
        result.protocol_version = ProtocolVersion::V_2024_11_05;
        result.server_info = Implementation::from_build_env();
        result.instructions = Some(
            "This server controls an antenna tracker. You can move it by steps or query its position."
                .to_string(),
        );

        Ok(result)
    }
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    AntennaServer::new()
        .serve(rmcp::transport::stdio())
        .await?
        .waiting()
        .await?;

    Ok(())
}
