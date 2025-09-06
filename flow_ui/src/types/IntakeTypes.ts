// Types that mirror your Python backend structure

export interface IntakeStep {
  name: string;
  ask_prompt: string;
  input_key: string;
  next_name: string | null;
  system_prompt?: string;
  validate_regex?: string;
  order_index: number;
}

export interface IntakeState {
  collected_data: Record<string, string>;
  current_step: string;
  completed_steps: string[];
  session_id: string;
  human_cursor: number;
  session_status?: 'active' | 'completed';
}

export interface SessionInfo {
  session_id: string;
  flow_name: string;
  state: IntakeState;
  connected: boolean;
}

export interface FlowEvent {
  type: 'step_started' | 'step_completed' | 'user_input' | 'ai_response' | 'flow_completed';
  step_name?: string;
  data?: any;
  timestamp: string;
}
