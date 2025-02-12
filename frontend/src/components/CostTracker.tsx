import React, { useState, useEffect, useMemo } from 'react';
import {
  Box,
  Paper,
  Typography,
  LinearProgress,
  Tooltip,
  IconButton,
} from '@mui/material';
import InfoIcon from '@mui/icons-material/Info';

// Token and cost constants
const MODEL_CONFIGS = {
  'gpt-3.5-turbo': {
    tokenLimit: 4000,
    inputCostPer1K: 0.0015,
    outputCostPer1K: 0.002,
    avgTokensPerChapter: 4000,  // Average tokens per chapter including prompt and response
  },
  'gpt-4': {
    tokenLimit: 8000,
    inputCostPer1K: 0.03,
    outputCostPer1K: 0.06,
    avgTokensPerChapter: 6000,  // Average tokens per chapter including prompt and response
  }
} as const;

interface CostTrackerProps {
  chapterCount: number;
  completedChapters: number;
  currentDate: string;
}

const CostTracker: React.FC<CostTrackerProps> = ({
  chapterCount,
  completedChapters,
  currentDate,
}) => {
  const [actualCost, setActualCost] = useState<number>(0);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedModel, setSelectedModel] = useState<keyof typeof MODEL_CONFIGS>('gpt-3.5-turbo');

  // Calculate projected cost using useMemo with more accurate token estimation
  const projectedCost = useMemo(() => {
    const config = MODEL_CONFIGS[selectedModel];
    const totalTokens = chapterCount * config.avgTokensPerChapter;
    
    // Assume 40% of tokens are input (prompt) and 60% are output (completion)
    const inputTokens = totalTokens * 0.4;
    const outputTokens = totalTokens * 0.6;
    
    const inputCost = (inputTokens / 1000) * config.inputCostPer1K;
    const outputCost = (outputTokens / 1000) * config.outputCostPer1K;
    
    return inputCost + outputCost;
  }, [chapterCount, selectedModel]);

  useEffect(() => {
    const fetchCosts = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/cost-summary/${currentDate}`);
        if (response.ok) {
          const data = await response.json();
          setActualCost(data.total_cost_usd);
          
          // Update selected model based on usage data if available
          if (data.model_usage) {
            const models = Object.keys(data.model_usage) as Array<keyof typeof MODEL_CONFIGS>;
            const mostUsedModel = models.reduce((a, b) => 
              (data.model_usage[a]?.calls || 0) > (data.model_usage[b]?.calls || 0) ? a : b
            );
            setSelectedModel(mostUsedModel);
          }
        }
      } catch (error) {
        console.error('Error fetching costs:', error);
      } finally {
        setIsLoading(false);
      }
    };

    fetchCosts();
  }, [currentDate, completedChapters]);

  const progressPercentage = (actualCost / projectedCost) * 100;

  return (
    <Paper
      sx={{
        position: 'fixed',
        bottom: 0,
        left: 0,
        right: 0,
        p: 2,
        backgroundColor: 'background.paper',
        boxShadow: 3,
        zIndex: 1000,
      }}
    >
      <Box sx={{ width: '100%', maxWidth: 1200, margin: '0 auto' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Typography variant="subtitle1" sx={{ flexGrow: 1 }}>
            Cost Tracker ({selectedModel})
          </Typography>
          <Tooltip title={`Using ${selectedModel} with ${MODEL_CONFIGS[selectedModel].tokenLimit} token limit. Costs are estimated based on average token usage per chapter.`}>
            <IconButton size="small">
              <InfoIcon fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
        
        <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
          <Box sx={{ flexGrow: 1, mr: 2 }}>
            <LinearProgress
              variant="buffer"
              value={isLoading ? 0 : progressPercentage}
              valueBuffer={100}
              sx={{ height: 10, borderRadius: 5 }}
            />
          </Box>
          <Box sx={{ minWidth: 200, display: 'flex', justifyContent: 'space-between' }}>
            <Typography variant="body2" color="text.secondary">
              Actual: ${actualCost.toFixed(3)}
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Projected: ${projectedCost.toFixed(3)}
            </Typography>
          </Box>
        </Box>
        
        <Typography variant="caption" color="text.secondary">
          {completedChapters} of {chapterCount} chapters completed
        </Typography>
      </Box>
    </Paper>
  );
};

export default CostTracker; 