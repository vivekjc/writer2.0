import React, { useState } from 'react';
import {
  Box,
  Typography,
  Paper,
  List,
  ListItem,
  ListItemText,
  Button,
  CircularProgress,
  Accordion,
  AccordionSummary,
  AccordionDetails,
  Divider,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import axios from 'axios';

interface ResponseBreakdownProps {
  chapters: any[];
  onBreakdownComplete: (breakdown: any[]) => void;
}

interface ResponsePlan {
  title: string;
  points: string[];
  wordCount: number;
}

interface ChapterResponses {
  chapterTitle: string;
  totalWordCount: number;
  responses: ResponsePlan[];
}

// Model configuration with token and word limits
const MODEL_CONFIGS = {
  'gpt-3.5-turbo': {
    totalTokenLimit: 4000,    // Total token limit
    reservedTokens: 1000,     // Reserved for prompt, overhead, etc.
    wordsPerToken: 0.75,      // Approximate words per token
    maxWordsPerResponse: 750  // (4000-1000) * 0.75 ≈ 750 words safe limit
  },
  'gpt-4': {
    totalTokenLimit: 8000,
    reservedTokens: 2000,
    wordsPerToken: 0.75,
    maxWordsPerResponse: 1500 // (8000-2000) * 0.75 ≈ 1500 words safe limit
  }
} as const;

// Helper functions for calculations
const calculateResponseLimits = (
  totalWords: number,
  model: keyof typeof MODEL_CONFIGS = 'gpt-3.5-turbo'
): { numResponses: number; wordsPerResponse: number } => {
  const config = MODEL_CONFIGS[model];
  
  // Calculate number of responses needed based on safe word limit
  let numResponses = Math.max(1, Math.ceil(totalWords / config.maxWordsPerResponse));
  
  // Distribute words evenly across responses, rounded up to nearest 10
  let wordsPerResponse = Math.ceil(totalWords / numResponses / 10) * 10;
  
  // Verify we're within token limits
  const estimatedTokens = Math.ceil(wordsPerResponse / config.wordsPerToken);
  if (estimatedTokens + config.reservedTokens > config.totalTokenLimit) {
    // If we exceed token limit, recalculate with one more chunk
    numResponses += 1;
    wordsPerResponse = Math.ceil(totalWords / numResponses / 10) * 10;
  }
  
  return { numResponses, wordsPerResponse };
};

const ResponseBreakdown: React.FC<ResponseBreakdownProps> = ({
  chapters,
  onBreakdownComplete,
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chapterResponses, setChapterResponses] = useState<ChapterResponses[]>([]);
  const [currentChapterIndex, setCurrentChapterIndex] = useState(-1);

  // Calculate total responses needed across all chapters
  const totalStats = chapters.reduce((stats, chapter) => {
    const { numResponses } = calculateResponseLimits(chapter.wordCount);
    return {
      totalResponses: stats.totalResponses + numResponses,
      totalWords: stats.totalWords + chapter.wordCount
    };
  }, { totalResponses: 0, totalWords: 0 });

  const generateResponseBreakdown = async (chapter: any, index: number) => {
    setLoading(true);
    setCurrentChapterIndex(index);
    setError(null);
    
    const maxRetries = 2;
    let retryCount = 0;
    
    while (retryCount <= maxRetries) {
      try {
        console.log('Generating response breakdown for chapter:', chapter);
        
        const { numResponses, wordsPerResponse } = calculateResponseLimits(chapter.wordCount);
        
        console.log(`Chapter "${chapter.title}" calculations:`, {
          totalWords: chapter.wordCount,
          numResponses,
          wordsPerResponse,
          estimatedTokens: Math.ceil(wordsPerResponse / MODEL_CONFIGS['gpt-3.5-turbo'].wordsPerToken),
          attempt: retryCount + 1
        });
        
        const requestData = {
          chapter_title: chapter.title,
          content: chapter.content || '',
          sections: chapter.sections || [],
          total_word_count: chapter.wordCount,
          response_word_limit: wordsPerResponse,
          expected_responses: numResponses // Add this to request
        };

        const response = await axios.post('http://localhost:8000/api/break-into-responses', requestData);
        console.log('Server response:', response.data);

        if (!response.data.responses || !Array.isArray(response.data.responses)) {
          throw new Error('Invalid response format from server');
        }

        // Verify response counts and word limits
        if (response.data.responses.length !== numResponses) {
          if (retryCount < maxRetries) {
            console.warn(`Response count mismatch - Expected: ${numResponses}, Got: ${response.data.responses.length}. Retrying...`);
            retryCount++;
            continue;
          }
          throw new Error(`Failed to generate the correct number of responses after ${maxRetries + 1} attempts. Expected: ${numResponses}, Got: ${response.data.responses.length}`);
        }

        // Verify total words across responses matches chapter word count
        const totalResponseWords = response.data.responses.reduce((sum: number, r: ResponsePlan) => sum + r.wordCount, 0);
        if (Math.abs(totalResponseWords - chapter.wordCount) > numResponses * 10) {
          console.warn(`Word count mismatch - Chapter: ${chapter.wordCount}, Sum of responses: ${totalResponseWords}`);
        }

        // Verify each response is within token limits
        response.data.responses.forEach((resp: ResponsePlan, idx: number) => {
          const estimatedTokens = Math.ceil(resp.wordCount / MODEL_CONFIGS['gpt-3.5-turbo'].wordsPerToken);
          if (estimatedTokens + MODEL_CONFIGS['gpt-3.5-turbo'].reservedTokens > MODEL_CONFIGS['gpt-3.5-turbo'].totalTokenLimit) {
            console.warn(`Response ${idx + 1} may exceed token limit:`, {
              wordCount: resp.wordCount,
              estimatedTokens,
              totalTokens: estimatedTokens + MODEL_CONFIGS['gpt-3.5-turbo'].reservedTokens,
              limit: MODEL_CONFIGS['gpt-3.5-turbo'].totalTokenLimit
            });
          }
        });

        setChapterResponses(prev => {
          const updated = [...prev];
          updated[index] = {
            chapterTitle: chapter.title,
            totalWordCount: chapter.wordCount,
            responses: response.data.responses
          };
          return updated;
        });
        
        // If we got here, we succeeded
        break;

      } catch (err: any) {
        console.error('Error details:', err);
        let errorMessage = `Error generating response breakdown (Attempt ${retryCount + 1}/${maxRetries + 1}). `;
        if (err.response?.data?.detail) {
          errorMessage += err.response.data.detail;
        } else if (err.message) {
          errorMessage += err.message;
        }
        
        if (retryCount < maxRetries) {
          console.warn(errorMessage + ' Retrying...');
          retryCount++;
          continue;
        }
        
        setError(errorMessage);
        break;
      }
    }
    
    setLoading(false);
  };

  const generateAllBreakdowns = async () => {
    setLoading(true);
    setError(null);
    setChapterResponses([]);

    try {
      console.log('Starting to generate breakdowns for chapters:', chapters);
      for (let i = 0; i < chapters.length; i++) {
        await generateResponseBreakdown(chapters[i], i);
      }
    } catch (err) {
      console.error('Error in generateAllBreakdowns:', err);
      setError('Failed to generate all response breakdowns. Please try again.');
    } finally {
      setLoading(false);
      setCurrentChapterIndex(-1);
    }
  };

  const handleComplete = () => {
    try {
      // Transform the response breakdowns into the format needed for book generation
      const completeBreakdown = chapters.map((chapter, index) => ({
        ...chapter,
        responses: chapterResponses[index]?.responses || []
      }));
      console.log('Complete breakdown:', completeBreakdown);
      onBreakdownComplete(completeBreakdown);
    } catch (err) {
      console.error('Error in handleComplete:', err);
      setError('Failed to process response breakdowns. Please try again.');
    }
  };

  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="h6" gutterBottom>
        Plan Responses
      </Typography>
      
      <Typography variant="body2" color="text.secondary" paragraph>
        Each chapter will be broken down into smaller responses based on the model's token limit. 
        For GPT-3.5-turbo, responses are limited to {MODEL_CONFIGS['gpt-3.5-turbo'].maxWordsPerResponse} words 
        to stay within the {MODEL_CONFIGS['gpt-3.5-turbo'].totalTokenLimit} token limit 
        (reserving {MODEL_CONFIGS['gpt-3.5-turbo'].reservedTokens} tokens for prompts and overhead).
      </Typography>

      <Box sx={{ mb: 3 }}>
        <Typography variant="body2" color="text.secondary">
          Total chapters: {chapters.length}
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Total word count: {totalStats.totalWords.toLocaleString()} words
        </Typography>
        <Typography variant="body2" color="text.secondary">
          Estimated responses: {totalStats.totalResponses} ({(totalStats.totalResponses / chapters.length).toFixed(1)} per chapter)
        </Typography>
      </Box>

      {error && (
        <Paper sx={{ p: 2, mb: 2, bgcolor: 'error.light' }}>
          <Typography color="error" variant="body1">
            {error}
          </Typography>
        </Paper>
      )}

      {!loading && currentChapterIndex === -1 && (
        <Button
          variant="contained"
          color="primary"
          onClick={generateAllBreakdowns}
          sx={{ mb: 3 }}
        >
          Generate Response Breakdowns
        </Button>
      )}

      {loading && (
        <Box sx={{ mb: 3 }}>
          <Typography variant="body2" gutterBottom>
            {currentChapterIndex !== -1 
              ? `Breaking down Chapter ${currentChapterIndex + 1} of ${chapters.length}`
              : 'Preparing to break down chapters...'}
          </Typography>
          <CircularProgress />
        </Box>
      )}

      <List>
        {chapterResponses.map((chapter, chapterIndex) => 
          chapter ? (
          <Accordion key={chapterIndex} sx={{ mb: 2 }}>
            <AccordionSummary expandIcon={<ExpandMoreIcon />}>
              <Box sx={{ display: 'flex', flexDirection: 'column', width: '100%' }}>
                <Typography>
                  {chapter.chapterTitle}
                </Typography>
                <Typography variant="body2" color="text.secondary">
                  {chapter.responses.length} responses, {chapter.totalWordCount.toLocaleString()} total words 
                  ({Math.ceil(chapter.totalWordCount / chapter.responses.length).toLocaleString()} words/response)
                </Typography>
              </Box>
            </AccordionSummary>
            <AccordionDetails>
              <List>
                {chapter.responses.map((response, responseIndex) => (
                  <Paper key={responseIndex} sx={{ mb: 2, p: 2 }}>
                    <Typography variant="subtitle1">
                      Response {responseIndex + 1}: {response.title}
                    </Typography>
                    <Box sx={{ mb: 1 }}>
                      <Typography variant="body2" color="text.secondary">
                        Target word count: {response.wordCount} words
                        {responseIndex === 0 && " (includes introduction)"}
                        {responseIndex === chapter.responses.length - 1 && " (includes conclusion and references)"}
                      </Typography>
                      <Typography variant="body2" color="text.secondary">
                        Estimated tokens: {Math.ceil(response.wordCount / MODEL_CONFIGS['gpt-3.5-turbo'].wordsPerToken)}
                        {" + "}{MODEL_CONFIGS['gpt-3.5-turbo'].reservedTokens} reserved
                      </Typography>
                    </Box>
                    <Divider sx={{ my: 1 }} />
                    <Typography variant="subtitle2" gutterBottom>
                      Points to Cover ({response.points.length} points, ~{Math.ceil(response.wordCount / response.points.length)} words each):
                    </Typography>
                    <List dense>
                      {response.points.map((point, pointIndex) => (
                        <ListItem key={pointIndex}>
                          <ListItemText 
                            primary={point}
                            secondary={`Estimated ${Math.ceil(response.wordCount / response.points.length)} words`}
                          />
                        </ListItem>
                      ))}
                    </List>
                  </Paper>
                ))}
              </List>
            </AccordionDetails>
          </Accordion>
          ) : null
        )}
      </List>

      {chapterResponses.length > 0 && (
        <Button
          variant="contained"
          color="primary"
          onClick={handleComplete}
          sx={{ mt: 2 }}
        >
          Confirm Response Breakdown
        </Button>
      )}
    </Box>
  );
};

export default ResponseBreakdown; 